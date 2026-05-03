# Feature: Neo4j Knowledge Graph Setup

**Status:** SPECIFIED
**Date:** 2026-04-01
**Author:** Feature Architect (AI-assisted)

## Problem

The lumber calculator hardcodes material specifications (`LUMBER_SPECS` dict in `lumber_calculator.py`) and embeds IRC code rules implicitly in calculation logic. This makes the data impossible to query, extend, or audit independently of the code. As the system grows to support agents, compliance checking, and provenance tracking, construction knowledge needs to live in an externalized, queryable graph — not scattered across Python dicts and if-statements.

## Goals

- Neo4j runs as a Docker Compose service alongside existing PostgreSQL, FastAPI, and React services
- Lumber specifications and IRC framing rules are stored as versioned graph nodes with full provenance
- All KG entities follow a universal versioning convention (version chains with rollback)
- The lumber calculator loads specs from Neo4j into an in-memory dict at startup (not per-query) for zero-latency lookups
- Takeoff results match ground truth projects with known stock quantities
- Seed data is idempotent and can be re-run safely
- KG schema is designed to extend naturally when agents are built later

## Non-Goals

- Full proposal KG schema (PlanSheet, PlanFact, AssemblyIntent, etc.) — expand later when agents exist
- Fallback to hardcoded data if Neo4j is unavailable — Neo4j is a hard dependency
- Agent framework or LLM integration
- Migration of project/drawing/takeoff data from PostgreSQL to Neo4j — PostgreSQL remains for relational data

## User Stories

- As a developer, I want lumber specs in Neo4j so that I can extend material data without changing Python code.
- As a developer, I want IRC code rules as graph nodes so that future compliance agents can query them with Cypher.
- As a developer, I want full version history on KG entities so that I can audit what changed, when, and roll back bad updates.
- As an end user, I want the same takeoff results I get today, sourced from the knowledge graph instead of hardcoded values.

## Design Approach

### Architecture

```
                    ┌─────────────┐
                    │   React UI  │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   FastAPI   │
                    │   Backend   │
                    └──┬──────┬───┘
                       │      │
              ┌────────▼┐  ┌──▼─────────┐
              │PostgreSQL│  │   Neo4j    │
              │(projects,│  │(materials, │
              │ drawings,│  │ code rules,│
              │ takeoffs)│  │ provenance)│
              └─────────┘  └────────────┘
```

PostgreSQL keeps relational/transactional data. Neo4j holds construction domain knowledge with version history.

### Components

1. **Docker service** — Neo4j 5.x container in `docker-compose.yml` with constrained heap (256MB for local dev)
2. **Connection client** — `backend/app/core/kg/client.py` with driver init, FastAPI dependency, startup verification
3. **Seed script** — `backend/app/core/kg/seed.py` with versioned, idempotent seed data for lumber specs, framing roles, and IRC rules
4. **Provenance module** — `backend/app/core/kg/provenance.py` with universal versioning convention and rollback support
5. **Spec loader** — `backend/app/core/kg/loader.py` loads current specs from Neo4j into an in-memory dict at startup
6. **Config additions** — `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` in Settings and `.env.example`
7. **Refactored calculator** — `lumber_calculator.py` receives pre-loaded spec dict (sourced from KG, but used as plain dict at runtime)

### Universal Versioning Convention

All KG entities follow this pattern. This convention is established now so that every future node type (PlanFact, AssemblyIntent, etc.) inherits it.

**Node properties (required on all versioned entities):**
```
{
  _version: int,          # monotonically increasing per entity identity
  _status: "ACTIVE" | "REVOKED",
  _created_at: datetime,  # ISO 8601
  _created_by: string,    # "seed", "api", user id, agent id
  _reason: string         # why this version was created
}
```

**Version chain relationship:**
```
(:LumberSpec {_version: 1, _status: "ACTIVE"})
  -[:SUPERSEDED_BY]->
(:LumberSpec {_version: 2, _status: "ACTIVE"})
```

**Resolving current version:**
```cypher
// Get current active LumberSpec for 2x4
MATCH (l:LumberSpec {nominal_width: 2, nominal_height: 4, _status: "ACTIVE"})
WHERE NOT (l)-[:SUPERSEDED_BY]->(:LumberSpec {_status: "ACTIVE"})
RETURN l
```

**Rollback:**
```cypher
// Revoke version 2, making version 1 current again
MATCH (l:LumberSpec {nominal_width: 2, nominal_height: 4, _version: 2})
SET l._status = "REVOKED"
```
After revoking, the "current version" query automatically resolves to the latest `ACTIVE` node that has no outgoing `SUPERSEDED_BY` to another `ACTIVE` node.

### KG Schema (Phase 1 — Minimal + Provenance)

```
(:LumberSpec {nominal: "2x4", nominal_width: 2, nominal_height: 4,
              actual_width: 1.5, actual_height: 3.5, grade: "STUD",
              _version: 1, _status: "ACTIVE", _created_at: ...,
              _created_by: "seed", _reason: "initial seed"})

(:FramingRole {name: "stud" | "plate" | "header",
               _version: 1, _status: "ACTIVE", ...})

(:CodeRule {code: "IRC", section: "R602.3",
            description: "...", max_spacing_in: 16, applies_to: "bearing_wall",
            _version: 1, _status: "ACTIVE", ...})

(:LumberSpec)-[:USED_AS]->(:FramingRole)
(:FramingRole)-[:GOVERNED_BY]->(:CodeRule)
(:LumberSpec)-[:SUPERSEDED_BY]->(:LumberSpec)  # version chain
```

Node types:
- **LumberSpec** — one versioned node per nominal size (2x4, 2x6, 2x8, 2x10, 2x12, 4x4)
- **FramingRole** — stud, plate, header (extensible to joist, rafter, etc.)
- **CodeRule** — IRC section references for framing requirements

Relationships:
- **USED_AS** — which lumber specs can fill which roles
- **GOVERNED_BY** — which roles are constrained by which code rules
- **SUPERSEDED_BY** — version chain linking old → new versions of any entity

### Data Flow (Refactored)

```
Backend startup:
  → verify_kg_connection()
  → seed_kg() (idempotent)
  → load_specs_from_kg() → populates in-memory dict (like today's LUMBER_SPECS)

POST /api/takeoff/process/{drawing_id}:
  → parse DXF/PDF → WallElement list
  → LumberCalculator(specs_dict, config)   # dict, not kg_session
      → specs_dict[(2, 4)]                  # O(1) dict lookup, same as before
      → calculate studs, plates
  → return LumberMaterialItem list (same schema as today)
```

The KG is the **source of truth**. The in-memory dict is a **runtime cache** loaded once at startup. This gives zero-latency lookups with externalized, auditable, versionable data.

## Sample Implementation

```python
# === backend/app/core/kg/provenance.py ===
# Universal versioning convention for all KG entities

from datetime import datetime, timezone

VERSION_PROPS = {
    "_version": 1,
    "_status": "ACTIVE",
    "_created_at": None,   # set at write time
    "_created_by": "seed",
    "_reason": "initial seed",
}

def create_versioned_node(tx, label, identity_props, data_props, created_by="seed", reason="initial seed"):
    """Create a new versioned node, or a new version if one exists.

    identity_props: properties that identify the logical entity (e.g., nominal_width, nominal_height)
    data_props: properties that can change between versions (e.g., actual_width, grade)
    """
    now = datetime.now(timezone.utc).isoformat()

    # Find current active version
    current = tx.run(
        f"MATCH (n:{label} {{_status: 'ACTIVE'}}) "
        f"WHERE {' AND '.join(f'n.{k} = ${k}' for k in identity_props)} "
        f"AND NOT (n)-[:SUPERSEDED_BY]->(:{label} {{_status: 'ACTIVE'}}) "
        f"RETURN n",
        **identity_props,
    ).single()

    all_props = {**identity_props, **data_props,
                 "_status": "ACTIVE", "_created_at": now,
                 "_created_by": created_by, "_reason": reason}

    if current is None:
        # First version
        all_props["_version"] = 1
        tx.run(f"CREATE (n:{label} $props)", props=all_props)
    else:
        # Check if data actually changed
        node = current["n"]
        if all(node.get(k) == v for k, v in data_props.items()):
            return  # No change, skip
        # New version
        all_props["_version"] = node["_version"] + 1
        tx.run(
            f"MATCH (old:{label}) WHERE elementId(old) = $old_id "
            f"CREATE (new:{label} $props) "
            f"CREATE (old)-[:SUPERSEDED_BY]->(new)",
            old_id=current["n"].element_id, props=all_props,
        )

def rollback_version(tx, label, identity_props, version):
    """Revoke a specific version, making the previous active version current."""
    tx.run(
        f"MATCH (n:{label} {{_version: $ver, _status: 'ACTIVE'}}) "
        f"WHERE {' AND '.join(f'n.{k} = ${k}' for k in identity_props)} "
        f"SET n._status = 'REVOKED'",
        ver=version, **identity_props,
    )


# === backend/app/core/kg/seed.py ===

from app.core.kg.provenance import create_versioned_node

LUMBER_SPECS = [
    {"identity": {"nominal_width": 2, "nominal_height": 4},
     "data": {"nominal": "2x4", "actual_width": 1.5, "actual_height": 3.5, "grade": "STUD"}},
    {"identity": {"nominal_width": 2, "nominal_height": 6},
     "data": {"nominal": "2x6", "actual_width": 1.5, "actual_height": 5.5, "grade": "STUD"}},
    {"identity": {"nominal_width": 2, "nominal_height": 8},
     "data": {"nominal": "2x8", "actual_width": 1.5, "actual_height": 7.25, "grade": "STUD"}},
    {"identity": {"nominal_width": 2, "nominal_height": 10},
     "data": {"nominal": "2x10", "actual_width": 1.5, "actual_height": 9.25, "grade": "STUD"}},
    {"identity": {"nominal_width": 2, "nominal_height": 12},
     "data": {"nominal": "2x12", "actual_width": 1.5, "actual_height": 11.25, "grade": "STUD"}},
    {"identity": {"nominal_width": 4, "nominal_height": 4},
     "data": {"nominal": "4x4", "actual_width": 3.5, "actual_height": 3.5, "grade": "NO2"}},
]

def seed_kg(session):
    with session.begin_transaction() as tx:
        for spec in LUMBER_SPECS:
            create_versioned_node(tx, "LumberSpec", spec["identity"], spec["data"])
        for role in ["stud", "plate", "header"]:
            create_versioned_node(tx, "FramingRole", {"name": role}, {})
        create_versioned_node(tx, "CodeRule",
            {"code": "IRC", "section": "R602.3"},
            {"description": "Bearing wall stud spacing", "max_spacing_in": 16,
             "applies_to": "bearing_wall"})
        tx.commit()
    # Relationships (idempotent via MERGE)
    session.run("""
        MATCH (l:LumberSpec {_status: "ACTIVE"}), (r:FramingRole {_status: "ACTIVE"})
        WHERE l.nominal_width = 2 AND l.nominal_height = 4
          AND r.name IN ["stud", "plate"]
          AND NOT (l)-[:SUPERSEDED_BY]->(:{_status: "ACTIVE"})
          AND NOT (r)-[:SUPERSEDED_BY]->(:{_status: "ACTIVE"})
        MERGE (l)-[:USED_AS]->(r)
    """)
    session.run("""
        MATCH (r:FramingRole {name: "stud", _status: "ACTIVE"}),
              (c:CodeRule {section: "R602.3", _status: "ACTIVE"})
        WHERE NOT (r)-[:SUPERSEDED_BY]->(:FramingRole {_status: "ACTIVE"})
          AND NOT (c)-[:SUPERSEDED_BY]->(:CodeRule {_status: "ACTIVE"})
        MERGE (r)-[:GOVERNED_BY]->(c)
    """)


# === backend/app/core/kg/loader.py ===

from app.schemas.material import LumberSpecification, LumberGrade

def load_lumber_specs(session) -> dict[tuple[int, int], LumberSpecification]:
    """Load current active specs from Neo4j into a dict. Called once at startup."""
    results = session.run("""
        MATCH (l:LumberSpec {_status: "ACTIVE"})
        WHERE NOT (l)-[:SUPERSEDED_BY]->(:LumberSpec {_status: "ACTIVE"})
        RETURN l
    """)
    specs = {}
    for record in results:
        n = record["l"]
        key = (n["nominal_width"], n["nominal_height"])
        specs[key] = LumberSpecification(
            nominal_width=n["nominal_width"], nominal_height=n["nominal_height"],
            actual_width=n["actual_width"], actual_height=n["actual_height"],
            grade=LumberGrade(n["grade"]),
        )
    return specs


# === Refactored LumberCalculator (key change) ===
# Constructor now takes a plain dict instead of kg_session.
# The dict was loaded from Neo4j at startup. Runtime lookups are O(1).

class LumberCalculator:
    def __init__(self, lumber_specs: dict, config=None):
        self.lumber_specs = lumber_specs  # {(2,4): LumberSpecification, ...}
        self.config = config or FramingConfig()

    # In calculate_all_walls():
    #   replace: stud_spec = self.LUMBER_SPECS[self.config.stud_size]
    #   with:    stud_spec = self.lumber_specs[self.config.stud_size]
    # Identical behavior, different data source.
```

## Edge Cases & Error Handling

### Neo4j Unavailable at Startup
- **Scenario**: Neo4j container hasn't finished starting when backend starts
- **Behavior**: `verify_kg_connection()` in startup event raises, backend logs error and exits. Docker Compose `depends_on` with healthcheck prevents this in normal operation.
- **Test**: Stop Neo4j container, start backend, verify it fails with clear error message

### Missing Lumber Spec in KG
- **Scenario**: Calculator requests a spec (e.g., 2x6) that wasn't seeded
- **Behavior**: `KeyError` on dict lookup, same as today. API returns 500 with detail.
- **Test**: Remove a spec from seed data, restart, run takeoff, verify error message

### Seed Script Run Multiple Times
- **Scenario**: `seed_kg()` called on every startup or manually re-run
- **Behavior**: `create_versioned_node` checks if data changed before creating new version. Identical data = no-op. Changed data = new version with SUPERSEDED_BY chain.
- **Test**: Run seed twice, verify node count unchanged. Modify a spec value, run seed, verify version 2 created.

### Rollback Bad Seed Update
- **Scenario**: A seed update introduces incorrect spec values
- **Behavior**: Call `rollback_version(tx, "LumberSpec", {"nominal_width": 2, "nominal_height": 4}, version=2)`. Sets `_status = "REVOKED"` on version 2. Current-version query resolves to version 1.
- **Test**: Seed, update, rollback, verify original values restored via loader.

### Concurrent Takeoff Requests
- **Scenario**: Multiple takeoff requests hit the calculator simultaneously
- **Behavior**: All requests read from the same in-memory dict. No Neo4j queries at request time. Thread-safe because dict is read-only after startup.
- **Test**: Send 10 concurrent takeoff requests, verify all return correct results

### Neo4j Heap on Constrained Dev Machines
- **Scenario**: Developer runs full docker-compose stack on a laptop with limited RAM
- **Behavior**: Neo4j heap capped at 256MB via `NEO4J_server_memory_heap_max__size=256m` in docker-compose environment. Sufficient for seed data volume.
- **Test**: `docker stats` shows Neo4j container using <300MB

## Acceptance Criteria

### AC-1: Neo4j Docker Service
- **Given** the docker-compose.yml includes a Neo4j service with 256MB heap limit
- **When** `docker-compose up` is run
- **Then** Neo4j is accessible on bolt://localhost:7687 and the browser on http://localhost:7474

### AC-2: Seed Data Loaded with Provenance
- **Given** Neo4j is running and seed script has executed
- **When** running `MATCH (l:LumberSpec {_status: "ACTIVE"}) WHERE NOT (l)-[:SUPERSEDED_BY]->(:LumberSpec {_status: "ACTIVE"}) RETURN count(l)`
- **Then** returns 6 (matching the 6 entries in current LUMBER_SPECS dict)
- **And** each node has `_version`, `_status`, `_created_at`, `_created_by`, `_reason` properties

### AC-3: Framing Roles and Code Rules
- **Given** seed data is loaded
- **When** running `MATCH (r:FramingRole {_status: "ACTIVE"})-[:GOVERNED_BY]->(c:CodeRule {_status: "ACTIVE"}) RETURN r, c`
- **Then** returns stud role governed by IRC R602.3

### AC-4: Ground Truth Parity
- **Given** Neo4j is running with seed data and specs loaded into memory
- **When** processing ground truth projects with known stock quantities
- **Then** the takeoff API returns material quantities matching the ground truth values

### AC-5: Hardcoded LUMBER_SPECS Removed
- **Given** the refactor is complete
- **When** searching for `LUMBER_SPECS` in `lumber_calculator.py`
- **Then** the hardcoded dict is gone; the class receives a dict parameter loaded from Neo4j

### AC-6: Config and Environment
- **Given** `.env.example` includes NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
- **When** a developer copies `.env.example` to `.env`
- **Then** the backend connects to Neo4j with default credentials

### AC-7: Startup Verification and Spec Loading
- **Given** the backend starts
- **When** the startup event fires
- **Then** `verify_kg_connection()` runs, seed data is loaded, and specs are loaded into memory dict

### AC-8: Version History
- **Given** a LumberSpec exists at version 1
- **When** the seed script is run with a changed value for that spec
- **Then** a version 2 node is created with `SUPERSEDED_BY` relationship from version 1
- **And** version 1 retains its original values
- **And** the loader returns version 2 values

### AC-9: Rollback
- **Given** a LumberSpec exists at version 2 (superseding version 1)
- **When** `rollback_version` is called on version 2
- **Then** version 2 is marked `_status: "REVOKED"`
- **And** the current-version query resolves to version 1
- **And** after reloading specs, the calculator uses version 1 values

### AC-10: Idempotent Seed
- **Given** seed data has been loaded
- **When** `seed_kg()` is called again with identical data
- **Then** no new nodes or versions are created

## Technical Notes

- **Affected files**:
  - `docker-compose.yml` — add Neo4j service with heap constraint
  - `backend/app/core/config.py` — add NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD settings
  - `backend/app/core/kg/__init__.py` — new file
  - `backend/app/core/kg/client.py` — new file, connection management
  - `backend/app/core/kg/provenance.py` — new file, universal versioning convention
  - `backend/app/core/kg/seed.py` — new file, seed data with provenance
  - `backend/app/core/kg/loader.py` — new file, load specs into memory dict
  - `backend/app/core/extraction/lumber_calculator.py` — refactor: remove LUMBER_SPECS class var, accept dict parameter
  - `backend/app/api/takeoff.py` — pass loaded specs dict to LumberCalculator
  - `backend/app/main.py` — add startup/shutdown hooks for Neo4j (verify, seed, load)
  - `backend/.env.example` — add Neo4j vars
  - `backend/requirements.txt` — add `neo4j` package
- **Patterns to follow**: `get_db()` dependency injection pattern, pydantic-settings for config, Docker Compose service with healthcheck
- **Data model**: PostgreSQL unchanged. Neo4j is additive — new data store for domain knowledge only.
- **Neo4j version**: 5.x (community edition, sufficient for single-instance dev)
- **Python driver**: `neo4j` (official, not neomodel OGM)
- **Versioning convention**: All future KG entities MUST follow the universal versioning pattern defined in `provenance.py`. This includes the `_version`, `_status`, `_created_at`, `_created_by`, `_reason` properties and the `SUPERSEDED_BY` relationship chain.

## Dependencies

- Docker and Docker Compose (already required)
- `neo4j` Python package (to be added to requirements.txt)
- Ground truth project data for verification (AC-4)
- No changes to frontend

## Open Questions

- Exact IRC code sections to seed beyond R602.3 — expand during implementation based on what the calculator logic currently encodes
- Whether to run seed on every startup or provide a separate CLI command — spec assumes startup for simplicity, with no-op behavior when data hasn't changed
- Neo4j authentication hardening for production/GCP deployment (current spec uses default credentials suitable for dev)
- Whether spec reload should be triggerable at runtime (e.g., after a KG update via API) or only at startup — spec assumes startup-only for now
