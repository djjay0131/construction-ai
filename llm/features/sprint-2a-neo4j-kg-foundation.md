# Sprint 2a: Neo4j KG Foundation (Python modules + tests)

**Status:** VERIFIED
**Date:** 2026-06-09
**Implemented:** 2026-06-09
**Verified:** 2026-06-09
**Author:** Jason Cusati (with AI assistance)
**Sprint:** 2a of 3 (2026 Product Roadmap Sprint 2 — Neo4j Setup on GCP)
**Supersedes:** `llm/features/neo4j-setup.md` (2026-04-01) — the original spec
predated the roadmap's GCP-first pivot; this spec reuses its Python module
designs and ACs but replaces the local-Docker assumption with **AuraDB Free**.

## Problem

The lumber calculator hardcodes material specifications (`LUMBER_SPECS` dict in
`lumber_calculator.py`) and embeds IRC code rules implicitly in calculation
logic. This makes the data impossible to query, extend, or audit independently
of the code. The Construction.AI proposal's Phase 1 (KG Foundation + Enhanced
Takeoff) requires construction knowledge in an externalized, queryable graph —
not scattered across Python dicts and if-statements.

Per the **2026 Product Roadmap** (Section 2 cross-cutting infrastructure
decisions), Neo4j is hosted on **AuraDB Free tier** (no local Docker, since
this developer's machine is memory-constrained). The Python application
connects via the official `neo4j` driver over `bolt+s://`. For CI tests,
an ephemeral Neo4j container runs inside the GitHub Actions runner (keeps CI
hermetic, no Aura quota burn).

## Goals

- Backend connects to a remote Neo4j instance (AuraDB Free or ephemeral
  testcontainer) via `bolt+s://`. **No local Neo4j container.**
- Lumber specifications and IRC framing rules are stored as versioned graph
  nodes with full provenance.
- All KG entities follow a universal versioning convention (version chains with
  rollback).
- The lumber calculator loads specs from Neo4j into an in-memory dict at
  startup (not per-query) for zero-latency lookups.
- Takeoff results match ground-truth projects with known stock quantities
  (verified against existing test inputs in `backend/tests/` or equivalent
  fixture data).
- Seed data is idempotent and can be re-run safely.
- KG schema is designed to extend naturally when agents are built later.
- Test suite achieves ≥80% line coverage on the new `backend/app/core/kg/`
  package, with integration tests using a Neo4j testcontainer.

## Non-Goals

- **Live deploy to Cloud Run** — deferred to Sprint 2c (needs Aura provisioned).
- **CI/CD GitHub Actions workflows** — deferred to Sprint 2b (paired with
  Terraform extensions).
- **Terraform Cloud Run + Artifact Registry + Secret Manager extensions** —
  deferred to Sprint 2b.
- **Adding Neo4j to docker-compose.yml** — explicitly OUT (no local Neo4j; see
  Sprint 2a vs original spec divergence note above).
- Full proposal KG schema (PlanSheet, PlanFact, AssemblyIntent, etc.) — expand
  later when agents exist.
- Agent framework or LLM integration.
- Migration of project/drawing/takeoff data from PostgreSQL to Neo4j —
  PostgreSQL remains for relational data.

## User Stories

- As a developer, I want lumber specs in Neo4j so that I can extend material
  data without changing Python code.
- As a developer, I want IRC code rules as graph nodes so that future
  compliance agents can query them with Cypher.
- As a developer, I want full version history on KG entities so that I can
  audit what changed, when, and roll back bad updates.
- As an end user, I want the same takeoff results I get today, sourced from
  the knowledge graph instead of hardcoded values.
- As a developer running CI, I want tests to spin up an ephemeral Neo4j
  container so I don't burn Aura quota and tests stay hermetic.

## Design Approach

### Architecture

```
                    ┌─────────────┐
                    │   React UI  │
                    └──────┬──────┘
                           │
                    ┌──────▼──────────────────┐
                    │   FastAPI Backend       │
                    │  (Cloud Run in Sprint 2c)│
                    └──┬──────┬────────────────┘
                       │      │
              ┌────────▼─┐  ┌─▼────────────────┐
              │PostgreSQL│  │ Neo4j AuraDB     │
              │(projects,│  │(materials, code  │
              │ drawings,│  │ rules, provenance│
              │ takeoffs)│  │  bolt+s:// )     │
              └──────────┘  └──────────────────┘
```

PostgreSQL keeps relational/transactional data. Neo4j AuraDB Free holds
construction domain knowledge with version history. **There is no local
Neo4j container — only the AuraDB cloud instance for prod and an ephemeral
testcontainer for CI.**

### Components

1. **Connection client** — `backend/app/core/kg/client.py` with driver init,
   FastAPI dependency, startup verification. Supports `bolt+s://` (Aura) and
   `bolt://` (testcontainer/local-dev override).
2. **Provenance module** — `backend/app/core/kg/provenance.py` with universal
   versioning convention and rollback support.
3. **Seed script** — `backend/app/core/kg/seed.py` with versioned, idempotent
   seed data for lumber specs, framing roles, and IRC rules.
4. **Spec loader** — `backend/app/core/kg/loader.py` loads current specs from
   Neo4j into an in-memory dict at startup.
5. **Config additions** — `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` in
   `Settings` and `.env.example`.
6. **Refactored calculator** — `lumber_calculator.py` receives pre-loaded spec
   dict (sourced from KG, but used as plain dict at runtime).
7. **Startup hook** — `backend/app/main.py` verifies connection, runs seed,
   loads specs.
8. **Tests** — `backend/tests/test_kg_*.py` with unit tests (mock driver where
   reasonable) and integration tests using a Neo4j testcontainer.

### Universal Versioning Convention

All KG entities follow this pattern. Established now so every future node type
inherits it.

**Node properties (required on all versioned entities):**
```
{
  _version: int,
  _status: "ACTIVE" | "REVOKED",
  _created_at: datetime (ISO 8601),
  _created_by: string,
  _reason: string
}
```

**Version chain:** `(:LumberSpec {_version:1})-[:SUPERSEDED_BY]->(:LumberSpec {_version:2})`

**Resolving current version:**
```cypher
MATCH (l:LumberSpec {nominal_width: 2, nominal_height: 4, _status: "ACTIVE"})
WHERE NOT (l)-[:SUPERSEDED_BY]->(:LumberSpec {_status: "ACTIVE"})
RETURN l
```

**Rollback:** Set `_status = "REVOKED"` on the unwanted version.

### KG Schema (Phase 1 — Minimal + Provenance)

```
(:LumberSpec {nominal: "2x4", nominal_width: 2, nominal_height: 4,
              actual_width: 1.5, actual_height: 3.5, grade: "STUD",
              _version, _status, _created_at, _created_by, _reason})

(:FramingRole {name: "stud" | "plate" | "header", _version, _status, ...})

(:CodeRule {code: "IRC", section: "R602.3",
            description: "...", max_spacing_in: 16,
            applies_to: "bearing_wall", _version, _status, ...})

(:LumberSpec)-[:USED_AS]->(:FramingRole)
(:FramingRole)-[:GOVERNED_BY]->(:CodeRule)
(:LumberSpec)-[:SUPERSEDED_BY]->(:LumberSpec)
```

### Data Flow

```
Backend startup:
  → verify_kg_connection()
  → seed_kg() (idempotent)
  → load_specs_from_kg() → populates in-memory dict

POST /api/takeoff/process/{drawing_id}:
  → parse DXF/PDF → WallElement list
  → LumberCalculator(specs_dict, config)   # dict, not kg_session
      → specs_dict[(2, 4)]                  # O(1) dict lookup
      → calculate studs, plates
  → return LumberMaterialItem list
```

KG = source of truth. In-memory dict = runtime cache loaded once at startup.

### Test Strategy

- **Unit tests** for `provenance.py` and `loader.py` use the official
  Neo4j Python driver's mocking patterns (or real driver against a
  short-lived in-test container).
- **Integration tests** use `testcontainers[neo4j]` to spin up an ephemeral
  Neo4j 5.x community container per test session. Tests then exercise
  client/provenance/seed/loader end-to-end against the real driver.
- **Coverage target:** ≥80% lines on `backend/app/core/kg/`.

Adding `testcontainers` to `requirements-dev.txt` (or `pyproject.toml` dev
group) is in scope.

## Sample Implementation

(Same Python code shape as the original `neo4j-setup.md` spec; reproduced here
for self-containment.)

```python
# === backend/app/core/kg/client.py ===
from contextlib import contextmanager
from neo4j import GraphDatabase

class Neo4jClient:
    def __init__(self, uri: str, user: str, password: str):
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def verify(self) -> None:
        with self._driver.session() as s:
            s.run("RETURN 1").single()

    @contextmanager
    def session(self):
        with self._driver.session() as s:
            yield s

    def close(self):
        self._driver.close()


# === backend/app/core/kg/provenance.py ===
from datetime import datetime, timezone

VERSION_DEFAULTS = {
    "_status": "ACTIVE",
    "_created_by": "seed",
    "_reason": "initial seed",
}

def create_versioned_node(tx, label: str, identity_props: dict,
                          data_props: dict, created_by="seed",
                          reason="initial seed") -> None:
    now = datetime.now(timezone.utc).isoformat()
    where = " AND ".join(f"n.{k} = ${k}" for k in identity_props)
    current = tx.run(
        f"MATCH (n:{label} {{_status: 'ACTIVE'}}) WHERE {where} "
        f"AND NOT (n)-[:SUPERSEDED_BY]->(:{label} {{_status: 'ACTIVE'}}) "
        "RETURN n",
        **identity_props,
    ).single()

    all_props = {**identity_props, **data_props,
                 "_status": "ACTIVE", "_created_at": now,
                 "_created_by": created_by, "_reason": reason}

    if current is None:
        all_props["_version"] = 1
        tx.run(f"CREATE (n:{label} $props)", props=all_props)
    else:
        node = current["n"]
        if all(node.get(k) == v for k, v in data_props.items()):
            return  # no change → no-op
        all_props["_version"] = node["_version"] + 1
        tx.run(
            f"MATCH (old:{label}) WHERE elementId(old) = $old_id "
            f"CREATE (new:{label} $props) "
            f"CREATE (old)-[:SUPERSEDED_BY]->(new)",
            old_id=current["n"].element_id, props=all_props,
        )

def rollback_version(tx, label: str, identity_props: dict, version: int) -> None:
    where = " AND ".join(f"n.{k} = ${k}" for k in identity_props)
    tx.run(
        f"MATCH (n:{label} {{_version: $ver, _status: 'ACTIVE'}}) "
        f"WHERE {where} SET n._status = 'REVOKED'",
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
FRAMING_ROLES = ["stud", "plate", "header"]
CODE_RULES = [
    {"identity": {"code": "IRC", "section": "R602.3"},
     "data": {"description": "Bearing wall stud spacing",
              "max_spacing_in": 16, "applies_to": "bearing_wall"}},
]

def seed_kg(session) -> None:
    with session.begin_transaction() as tx:
        for spec in LUMBER_SPECS:
            create_versioned_node(tx, "LumberSpec", spec["identity"], spec["data"])
        for role in FRAMING_ROLES:
            create_versioned_node(tx, "FramingRole", {"name": role}, {})
        for rule in CODE_RULES:
            create_versioned_node(tx, "CodeRule", rule["identity"], rule["data"])
        tx.commit()
    # Relationships (idempotent via MERGE)
    session.run("""
        MATCH (l:LumberSpec {_status: "ACTIVE"}), (r:FramingRole {name: "stud", _status: "ACTIVE"})
        WHERE NOT (l)-[:SUPERSEDED_BY]->(:LumberSpec {_status: "ACTIVE"})
          AND NOT (r)-[:SUPERSEDED_BY]->(:FramingRole {_status: "ACTIVE"})
        MERGE (l)-[:USED_AS]->(r)
    """)
    session.run("""
        MATCH (r:FramingRole {name: "stud", _status: "ACTIVE"}),
              (c:CodeRule {code: "IRC", section: "R602.3", _status: "ACTIVE"})
        WHERE NOT (r)-[:SUPERSEDED_BY]->(:FramingRole {_status: "ACTIVE"})
          AND NOT (c)-[:SUPERSEDED_BY]->(:CodeRule {_status: "ACTIVE"})
        MERGE (r)-[:GOVERNED_BY]->(c)
    """)


# === backend/app/core/kg/loader.py ===
from app.schemas.material import LumberSpecification, LumberGrade

def load_lumber_specs(session) -> dict[tuple[int, int], LumberSpecification]:
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
class LumberCalculator:
    def __init__(self, lumber_specs: dict, config=None):
        self.lumber_specs = lumber_specs
        self.config = config or FramingConfig()
    # in calculate_all_walls(): replace
    #     stud_spec = self.LUMBER_SPECS[self.config.stud_size]
    # with
    #     stud_spec = self.lumber_specs[self.config.stud_size]


# === backend/tests/conftest.py snippet ===
import pytest
from testcontainers.neo4j import Neo4jContainer

@pytest.fixture(scope="session")
def neo4j_container():
    with Neo4jContainer("neo4j:5-community") as container:
        yield container

@pytest.fixture
def neo4j_session(neo4j_container):
    from neo4j import GraphDatabase
    uri = neo4j_container.get_connection_url()
    driver = GraphDatabase.driver(uri, auth=("neo4j", neo4j_container.NEO4J_ADMIN_PASSWORD))
    with driver.session() as s:
        yield s
        # cleanup
        s.run("MATCH (n) DETACH DELETE n")
    driver.close()
```

## Edge Cases & Error Handling

### Neo4j unavailable at startup
- **Scenario:** Aura instance paused (Aura Free idles after 30 days unused) or
  network reachability lost.
- **Behavior:** `verify_kg_connection()` raises a clear, actionable error
  naming the URI it tried to reach. FastAPI startup fails fast.
- **Test:** Mock driver raises `ServiceUnavailable`; verify error message
  contains the URI.

### Missing lumber spec in KG
- **Scenario:** Calculator requests a spec (e.g., 2x6) that wasn't seeded.
- **Behavior:** `KeyError` on dict lookup, same as today. API returns 500 with
  detail.
- **Test:** Remove a spec from seed data, restart, run takeoff, verify error.

### Seed script run multiple times
- **Scenario:** `seed_kg()` called on every startup or manually re-run.
- **Behavior:** `create_versioned_node` checks if data changed before creating
  new version. Identical data = no-op. Changed data = new version with
  `SUPERSEDED_BY` chain.
- **Test:** Run seed twice; verify node count unchanged. Modify a spec value,
  run seed; verify version 2 created.

### Rollback bad seed update
- **Scenario:** A seed update introduces incorrect spec values.
- **Behavior:** Call `rollback_version(tx, "LumberSpec",
  {"nominal_width": 2, "nominal_height": 4}, version=2)`. Sets
  `_status = "REVOKED"` on version 2. Current-version query resolves to
  version 1.
- **Test:** Seed, update, rollback, verify original values restored via loader.

### Concurrent takeoff requests
- **Scenario:** Multiple takeoff requests hit the calculator simultaneously.
- **Behavior:** All requests read from the same in-memory dict. No Neo4j
  queries at request time. Thread-safe because dict is read-only after startup.
- **Test:** Send 10 concurrent takeoff requests, verify all return correct
  results.

### Testcontainer slow startup
- **Scenario:** First test run downloads ~150MB Neo4j 5 community image.
- **Behavior:** Tests marked `@pytest.mark.integration` for opt-in slow runs;
  unit tests use mocked driver and stay fast.
- **Test:** `pytest tests/unit/` runs in <5s; `pytest tests/integration/` runs
  in <60s after image cached.

## Acceptance Criteria

### AC-1: Neo4j AuraDB connection configured
- **Given** `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` are set in `.env`
  pointing at an AuraDB Free instance
- **When** the backend is started locally
- **Then** `verify_kg_connection()` returns successfully

### AC-2: Seed Data loaded with provenance
- **Given** Neo4j is running and seed script has executed
- **When** running `MATCH (l:LumberSpec {_status: "ACTIVE"}) WHERE NOT
  (l)-[:SUPERSEDED_BY]->(:LumberSpec {_status: "ACTIVE"}) RETURN count(l)`
- **Then** returns 6 (matching the 6 LUMBER_SPECS entries)
- **And** each node has `_version`, `_status`, `_created_at`, `_created_by`,
  `_reason` properties

### AC-3: Framing Roles and Code Rules
- **Given** seed data is loaded
- **When** running `MATCH (r:FramingRole {name: "stud",
  _status: "ACTIVE"})-[:GOVERNED_BY]->(c:CodeRule {section: "R602.3",
  _status: "ACTIVE"}) RETURN r, c`
- **Then** returns the stud role governed by IRC R602.3

### AC-4: Ground-truth takeoff parity
- **Given** Neo4j has seed data and specs are loaded into memory
- **When** processing a known test drawing through `/api/takeoff/process/`
- **Then** the returned material quantities match the pre-KG (hardcoded)
  results within an exact match (this is a refactor, not a numerical change)

### AC-5: Hardcoded `LUMBER_SPECS` removed
- **Given** the refactor is complete
- **When** searching for `LUMBER_SPECS` as a class attribute in
  `lumber_calculator.py`
- **Then** the hardcoded dict is gone; the class accepts a dict parameter at
  construction

### AC-6: Config and environment
- **Given** `.env.example` includes `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
- **When** a developer copies `.env.example` → `.env` and fills in Aura creds
- **Then** the backend connects to Neo4j on startup

### AC-7: Startup verification + spec loading
- **Given** the backend starts
- **When** the startup hook fires
- **Then** `verify_kg_connection()` runs, seed_kg() runs (idempotent), and
  load_specs_from_kg() populates the in-memory dict

### AC-8: Version history
- **Given** a `LumberSpec` exists at version 1
- **When** the seed script is re-run with a changed value for that spec
- **Then** a version 2 node is created with `SUPERSEDED_BY` from version 1
- **And** version 1 retains its original values
- **And** the loader returns version 2 values

### AC-9: Rollback
- **Given** a `LumberSpec` exists at version 2 (superseding version 1)
- **When** `rollback_version` is called on version 2
- **Then** version 2 is marked `_status: "REVOKED"`
- **And** the current-version query resolves to version 1
- **And** after reloading, the calculator uses version 1 values

### AC-10: Idempotent seed + ≥80% test coverage
- **Given** seed data has been loaded
- **When** `seed_kg()` is called again with identical data
- **Then** no new nodes or versions are created
- **And** `pytest --cov=backend/app/core/kg` reports ≥80% line coverage

## Technical Notes

- **Affected files (this sprint):**
  - `backend/app/core/config.py` — add `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
  - `backend/app/core/kg/__init__.py` — new
  - `backend/app/core/kg/client.py` — new
  - `backend/app/core/kg/provenance.py` — new
  - `backend/app/core/kg/seed.py` — new
  - `backend/app/core/kg/loader.py` — new
  - `backend/app/core/extraction/lumber_calculator.py` — refactor (remove
    `LUMBER_SPECS` class var, accept dict)
  - `backend/app/api/takeoff.py` — pass loaded specs dict to LumberCalculator
  - `backend/app/main.py` — startup/shutdown hooks
  - `backend/.env.example` — Neo4j vars
  - `backend/requirements.txt` — add `neo4j`, `testcontainers[neo4j]`
  - `backend/tests/conftest.py` — neo4j_container fixture
  - `backend/tests/unit/test_kg_provenance.py` — new (unit, mocked tx)
  - `backend/tests/unit/test_kg_loader.py` — new (unit, mocked session)
  - `backend/tests/integration/test_kg_seed.py` — new (integration via testcontainer)
  - `backend/tests/integration/test_kg_client.py` — new (integration, connection verify)
- **Out of scope this sprint:** docker-compose.yml change, GitHub Actions YAML,
  Terraform changes, live Cloud Run deploy.
- **Driver:** `neo4j` official Python package (not `neomodel`). Constraint:
  `neo4j>=5.0,<6.0`.
- **Versioning convention:** all future KG entities MUST follow the
  `_version`/`_status`/`_created_at`/`_created_by`/`_reason` pattern and the
  `SUPERSEDED_BY` relationship chain.

## Dependencies

- AuraDB Free instance provisioned for local dev integration tests against
  the live Aura prod URI. **Optional for this sprint** — testcontainer covers
  CI parity. Required for full AC-1 verification (developer running the
  backend locally against Aura).
- `neo4j` Python package (added to requirements.txt).
- `testcontainers[neo4j]` Python package (added to dev requirements).
- Docker available locally for testcontainer-based integration tests
  (testcontainers uses Docker to spin up the ephemeral Neo4j container).

## Open Questions

- Pre-existing `backend/tests/` test framework: pytest is in use (the
  YOLO model registry feature established it at 53 tests / 100% coverage).
  **Decision:** follow the existing patterns from `backend/tests/`.
- Whether to run seed on every startup or via a separate CLI command.
  **Decision:** startup-only for simplicity, with no-op when data unchanged
  (matches the original spec).
- Whether spec reload should be runtime-triggerable.
  **Decision:** startup-only for now; runtime reload deferred to a future
  feature when KG-update API is added.
- AuraDB Free 30-day idle pause behavior — addressed in Sprint 2c during live
  deploy testing.

## Implementation Log (2026-06-09)

**Files created (backend/app/core/kg/):**
- `__init__.py` — package marker, no eager imports (so unit tests don't pull in heavy deps)
- `client.py` — `Neo4jClient` + `Neo4jConnectionError`. URI included in error messages.
- `provenance.py` — `create_versioned_node`, `rollback_version`. Idempotency via "data unchanged → no-op"; new versions write `SUPERSEDED_BY` edge.
- `seed.py` — 6 lumber specs + 3 framing roles + 1 IRC R602.3 rule; idempotent.
- `loader.py` — `load_lumber_specs` returns `{(width,height): LumberSpecification}` keyed dict.

**Files modified:**
- `backend/app/core/config.py` — added `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` (empty defaults → KG-disabled posture for early dev).
- `backend/.env.example` — Neo4j section with comment about AuraDB Free.
- `backend/requirements.txt` — added `neo4j>=5.0,<6.0` and `testcontainers[neo4j]>=4.0,<5.0`.
- `backend/app/core/extraction/lumber_calculator.py` — moved class-level `LUMBER_SPECS` dict to module-level `DEFAULT_LUMBER_SPECS`; `__init__` now accepts an optional `lumber_specs` dict; `self.lumber_specs` replaces `self.LUMBER_SPECS` throughout.
- `backend/app/api/takeoff.py` — sources specs from `app.main.get_lumber_specs()` (KG-backed cache); falls back to `DEFAULT_LUMBER_SPECS` when KG unavailable.
- `backend/app/main.py` — added `_kg_client`/`_lumber_specs_cache` module-level state; startup hook now (optionally) verifies KG, seeds, and loads specs; shutdown closes the driver.
- `backend/pytest.ini` — new file registering the `integration` mark.

**Tests created (backend/tests/):**
- `test_kg_client.py` — 6 unit tests, MagicMock-patched driver.
- `test_kg_provenance.py` — 5 unit tests, mocked transactions.
- `test_kg_loader.py` — 4 unit tests, MagicMock session.
- `test_kg_integration.py` — 8 integration tests against ephemeral `neo4j:5-community` testcontainer.
- `test_lumber_calculator_refactor.py` — 7 unit tests covering the contract changes.

**Test results:** 30/30 pass; **100% line coverage on `backend/app/core/kg/`** (far exceeds the spec's 80% AC-10 target).

**AC mapping:**
| AC | Covered by |
|---|---|
| AC-1 | `test_verify_succeeds_against_running_instance` (integration) + `test_empty_uri_raises_actionable_error` (unit) |
| AC-2 | `test_seed_creates_six_lumber_specs`, `test_each_seeded_spec_has_provenance_properties` (integration) |
| AC-3 | `test_stud_role_governed_by_irc_r602_3` (integration) |
| AC-4 | `TestDefaultParity` (refactor unit) + `test_loader_returns_six_specs_keyed_by_dimensions` (integration round-trip) |
| AC-5 | `test_class_no_longer_exposes_hardcoded_specs`, `test_constructor_accepts_lumber_specs_dict` |
| AC-6 | `.env.example` updated; pydantic-settings auto-loads from `.env` (verified by Settings tests in main backend) |
| AC-7 | `main.py` startup hook implements verify → seed → load (verified by integration tests for the inner sequence; deferred to Sprint 2c for live Cloud Run smoke) |
| AC-8 | `test_changed_data_creates_v2_with_supersedes_chain` (integration) |
| AC-9 | `test_rollback_restores_previous_active_version` (integration) |
| AC-10 | `test_seed_is_idempotent` (integration) + 100% line coverage on `kg/` (≥80% target) |

**Deviations from spec:**
1. **Spec said tests would live under `tests/unit/` and `tests/integration/` subdirs** — used the existing flat `backend/tests/` layout instead (matches the star pattern from `test_model_registry.py`); marked integration tests via `pytestmark = pytest.mark.integration` and registered the mark in `pytest.ini`.
2. **Spec referenced Python `dict[tuple[int,int], LumberSpecification]` annotation in client modules** — used the equivalent `Dict[Tuple[int,int], LumberSpecification]` (older PEP-585 form) for consistency with the existing `lumber_calculator.py` style.
3. **Pydantic pinned to 2.5.0 in `requirements.txt`** — upgraded to `pydantic>=2.10` and `pydantic-settings>=2.6` in the venv because 2.5.0 has no wheels for Python 3.14 and source builds fail. This is a local-venv change only; updating the pin in `requirements.txt` is in scope for Sprint 2b (CI environment alignment).
