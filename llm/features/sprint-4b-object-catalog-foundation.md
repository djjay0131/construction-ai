# Sprint 4b: Object Catalog Foundation (Builder + Store + Spatial Association)

**Status:** IMPLEMENTED
**Date:** 2026-06-14
**Implemented:** 2026-06-14
**Author:** Jason Cusati (with AI assistance)
**Sprint:** 4b of 2 (Sprint 4 — OCR Dimension Extraction & Object Catalog)
**Supersedes:** the "catalog construction + persistence + spatial
association" slice of `llm/features/ocr-dimension-extraction.md`
(SPECIFIED 2026-04-01). Builds on Sprint 4a (DimensionParser +
DimensionExtractor VERIFIED 2026-06-14).

## Problem

Sprint 4a parses OCR text into structured dimensions. To make those
dimensions useful, the takeoff pipeline needs:

1. A way to associate each parsed dimension with the architectural
   element it labels (the nearest wall, door, etc.).
2. A structured object graph that records every detected element,
   their relationships, and the OCR dimensions attached.
3. Persistence so the graph survives across reprocesses.

The parent spec calls for NetworkX. **Sprint 4b uses a plain-dict graph
representation instead** — per the parent's "Storage Format Experiment"
section ("Until then, default to JsonCatalogStore"). Dict-graph keeps
the scope small, avoids a new runtime dependency we may not need, and
maps cleanly to NetworkX or Neo4j later via the abstract `CatalogStore`
interface.

## Goals

- `SpatialAssociator` assigns each `ParsedDimension` from Sprint 4a to
  the nearest architectural element (Wall, Door, Window, Opening) by
  bbox-centroid distance, returning `(element_id, dimension)` pairs.
- `ObjectCatalogBuilder` constructs a `Catalog` (nodes + edges) from:
  wall segments (from Sprint 3b), YOLO detections (Sprint 3b
  Detection class), parsed dimensions (Sprint 4a). Computes wall-wall
  `CONNECTS_TO` and wall-opening `CONTAINS` edges; attaches dimensions
  to nodes; flags geometric-vs-OCR discrepancies (>15% diff per parent
  AC-6).
- `CatalogStore` serialises `Catalog` to JSON (`save`) and reads it
  back to an equivalent `Catalog` (`load`). Round-trip preserves all
  data.
- ≥80% line coverage; zero regression in the 184 Sprint 2/3/4a tests.

## Non-Goals

- **NetworkX** — not in this cycle. Parent's "Storage Format
  Experiment" explicitly allows deferring it. The interface is shaped
  so a `NetworkxCatalogStore` can be swapped in later.
- **Real EasyOCR reader** wrapping `FloorPlanAnalysisService` — out of
  scope; needs real image fixtures and integration smoke. Tests use the
  Sprint 4a Protocol-based fake.
- **Takeoff pipeline integration** — `LumberCalculator` reads from
  `Catalog`; deferred to a follow-up that has the e2e image fixtures.
- **`/api/catalog/{drawing_id}` endpoint** — deferred along with takeoff
  integration.
- **Multi-version / catalog history** — parent spec's open question;
  overwrite-on-save is fine for v1.
- **Room nodes** — deferred (parent spec also calls room nodes
  optional / open question).

## Design Approach

### Data model

```python
@dataclass(frozen=True)
class CatalogNode:
    id: str             # "wall_0", "door_1", "window_2", ...
    kind: str           # "wall" | "door" | "window" | "opening"
    bbox_px: tuple[int, int, int, int]
    length_in: float | None       # walls only; geometric primary
    length_source: str | None     # "geometric" | "ocr_fallback" | None
    ocr_dimension_in: float | None
    ocr_validation: str | None    # "confirmed" | "minor_discrepancy" | "mismatch" | None
    width_in: float | None        # doors/windows/openings
    height_in: float | None       # doors/windows
    confidence: float
    flags: tuple[str, ...]        # validation flags; tuple so frozen

@dataclass(frozen=True)
class CatalogEdge:
    src: str
    dst: str
    kind: str           # "CONNECTS_TO" | "CONTAINS"
    props: dict[str, Any] = field(default_factory=dict)

@dataclass
class Catalog:
    nodes: dict[str, CatalogNode]
    edges: list[CatalogEdge]
    metadata: dict[str, Any] = field(default_factory=dict)
```

### `SpatialAssociator`

```python
class SpatialAssociator:
    def __init__(self, max_distance_px: float = 200.0): ...

    def associate(
        self,
        dimensions: Sequence[ParsedDimension],
        candidates: Sequence[CatalogNode],
    ) -> list[tuple[str, ParsedDimension]]:
        """Return (node_id, dimension) pairs for each dimension whose
        bbox-centroid distance to a candidate node is within
        max_distance_px. Each dimension is paired with at most one node
        (the nearest). Ambiguous ties are broken by the larger candidate
        bbox (more likely a wall than a window)."""
```

### `ObjectCatalogBuilder`

```python
class ObjectCatalogBuilder:
    def __init__(
        self,
        associator: SpatialAssociator | None = None,
        connection_tolerance_px: float = 10.0,
        discrepancy_threshold: float = 0.15,
    ): ...

    def build(
        self,
        wall_segments: Sequence[PixelSegment],
        detections: Sequence[Detection],
        dimensions: Sequence[ParsedDimension],
        scale_px_per_in: float | None = None,
    ) -> Catalog:
        """Construct a Catalog from raster pipeline outputs."""
```

Algorithm:
1. Create one `Wall` node per `wall_segments` entry (id `wall_0`,
   `wall_1`, …). Compute `length_in` from segment length / scale.
2. Create one `Door`/`Window`/`Opening` node per matching YOLO
   detection (id `door_0`, etc.). Width/height from bbox.
3. **CONNECTS_TO** edges: for each pair of walls whose endpoints are
   within `connection_tolerance_px`, add an edge.
4. **CONTAINS** edges: for each opening, find the wall whose bbox
   contains the opening's centroid; add edge.
5. Use the associator to attach `ParsedDimension`s. For walls,
   compare attached OCR dim against geometric `length_in`. If
   `|ocr - geom| / geom > discrepancy_threshold` → set
   `ocr_validation = "mismatch"` and add `"ocr_geometry_mismatch"` to
   `flags`. If within 10% → `"confirmed"`. Between → `"minor_discrepancy"`.

### `CatalogStore`

```python
class CatalogStore:
    def save(self, catalog: Catalog, path: str | Path) -> None: ...
    def load(self, path: str | Path) -> Catalog: ...

    # JSON form: {"nodes": {id: {...}}, "edges": [{...}], "metadata": {...}}
```

Round-trip property: `load(save(c)) == c`. Tested.

### Discrepancy thresholds

* `<10%` difference → `confirmed`.
* `10–15%` difference → `minor_discrepancy`.
* `>15%` difference → `mismatch` + `"ocr_geometry_mismatch"` flag.

Matches parent spec's AC-6 wording.

## Edge Cases & Error Handling

### Empty inputs
- **Scenario:** No walls, no detections, no dimensions.
- **Behavior:** Builder returns `Catalog(nodes={}, edges=[], metadata={})`.
- **Test:** Explicit.

### No scale (`scale_px_per_in=None`)
- **Scenario:** Caller didn't run the scale detector successfully.
- **Behavior:** Walls get `length_in=None`, `length_source=None`. OCR
  dimensions still attach via the associator, but no
  geometric-vs-OCR validation (`ocr_validation=None`).
- **Test:** Explicit.

### Dimension too far from any element
- **Scenario:** `min_distance_to_element > max_distance_px`.
- **Behavior:** Dimension is dropped from associations (the catalog
  doesn't gain a node attachment for it).
- **Test:** Explicit — far-away dimension, verify it's not attached.

### Ambiguous association — two candidates equidistant
- **Scenario:** Two walls equidistant from a dimension's centroid.
- **Behavior:** Prefer the larger candidate bbox (more area = more
  likely a wall than an opening). Equal areas: pick the first by id
  (deterministic).
- **Test:** Both branches.

### Two walls share an endpoint
- **Scenario:** Wall A's end == Wall B's start (within tolerance).
- **Behavior:** Single `CONNECTS_TO` edge between them.
- **Test:** Two walls at right angles sharing a corner.

### Opening inside multiple wall bboxes
- **Scenario:** Door near the intersection of two walls.
- **Behavior:** Attach to the wall whose centerline is closer (smaller
  perpendicular distance from the opening centroid to the wall
  segment).
- **Test:** Explicit.

### Round-trip preserves dimensions
- **Scenario:** Catalog with `length_in=12.3456` and various float
  fields.
- **Behavior:** `load(save(c)) == c` to machine precision.
- **Test:** Explicit deep-equality after round-trip.

### Save to non-existent directory
- **Scenario:** Parent directory doesn't exist.
- **Behavior:** `save` creates it via `Path.mkdir(parents=True,
  exist_ok=True)`.
- **Test:** Use tmp_path/nested/dir.

### Load from non-existent file
- **Scenario:** Path doesn't exist.
- **Behavior:** `FileNotFoundError` propagates (don't swallow).
- **Test:** Explicit.

### Load corrupt JSON
- **Scenario:** File exists but isn't valid JSON.
- **Behavior:** `json.JSONDecodeError` propagates.
- **Test:** Write garbage, expect raise.

## Acceptance Criteria

### AC-1: Builder happy path
- **Given** 2 wall segments, 1 door detection, 0 dimensions, a scale
- **When** `build(...)` is called
- **Then** result has 3 nodes (`wall_0`, `wall_1`, `door_0`); each wall
  has `length_in > 0` and `length_source="geometric"`

### AC-2: Builder without scale
- **Given** the same inputs but `scale_px_per_in=None`
- **When** `build(...)` is called
- **Then** wall nodes have `length_in=None`, `length_source=None`

### AC-3: Wall–wall CONNECTS_TO edges
- **Given** 2 wall segments sharing an endpoint within tolerance
- **When** `build(...)` is called
- **Then** result has exactly one `CONNECTS_TO` edge between them

### AC-4: Wall–opening CONTAINS edges
- **Given** 1 wall segment + 1 door detection whose bbox centroid sits
  inside the wall's bbox
- **When** `build(...)` is called
- **Then** result has one `CONTAINS` edge from `wall_0` to `door_0`

### AC-5: SpatialAssociator nearest match
- **Given** 3 candidate nodes at different distances from a dimension's
  centroid, all within `max_distance_px`
- **When** `associate(...)` is called
- **Then** the dimension is paired with the nearest candidate

### AC-6: SpatialAssociator distance-cap drops far dimensions
- **Given** a dimension whose nearest candidate is beyond
  `max_distance_px`
- **When** `associate(...)` is called
- **Then** that dimension is not included in the output

### AC-7: OCR validates within 10% → `confirmed`
- **Given** a wall with `length_in=150.3` and OCR
  `ParsedDimension.inches=150.0` (~0.2% diff)
- **When** `build(...)` is called
- **Then** the wall has `ocr_validation="confirmed"`, no
  `"ocr_geometry_mismatch"` flag

### AC-8: OCR mismatch >15% → flagged
- **Given** a wall with `length_in=100.0` and OCR
  `ParsedDimension.inches=200.0` (100% diff)
- **When** `build(...)` is called
- **Then** the wall has `ocr_validation="mismatch"` and
  `"ocr_geometry_mismatch"` in `flags`

### AC-9: CatalogStore round-trip preserves data
- **Given** a `Catalog` with nodes + edges + metadata
- **When** `CatalogStore().save(c, path)` then `load(path)` runs
- **Then** the result equals the original

### AC-10: ≥80% line coverage + Sprint 2/3/4a regression
- **Given** the implementation is complete
- **When** the new test files run with coverage
- **Then** ≥80% on each new module
- **And** all 184 Sprint 2/3/4a tests still pass

## Technical Notes

- **Affected files:**
  - `backend/app/core/catalog/__init__.py` (new — package marker)
  - `backend/app/core/catalog/spatial_association.py` (new)
  - `backend/app/core/catalog/catalog_builder.py` (new)
  - `backend/app/core/catalog/catalog_store.py` (new)
  - `backend/tests/test_spatial_association.py` (new)
  - `backend/tests/test_catalog_builder.py` (new)
  - `backend/tests/test_catalog_store.py` (new)
  - `.github/workflows/ci.yml` (add the 3 new test files + 3 cov targets)
- **No new runtime dependencies.** Stdlib only (`json`, `pathlib`,
  `math`, `dataclasses`).
- **Future enhancement path:** `NetworkxCatalogStore` reads the same
  JSON, returns a `networkx.Graph` view; consumers that need graph
  algorithms (centrality, shortest path) opt in.

## Dependencies

- Sprint 3b VERIFIED (`WallLineExtractor` + `Detection` shape, `Sprint
  3a's CoordinateConverter` for the wall-segment shape).
- Sprint 4a VERIFIED (`ParsedDimension`).

## Open Questions

- Should `CatalogStore` enforce a schema version? **Decision:** v1 just
  records `"schema_version": "4b-v1"` in metadata. Future formats can
  branch on it.
- Should `Catalog` be immutable? **Decision:** no — builders mutate
  nodes/edges during construction. Once returned, callers shouldn't
  modify, but Python doesn't enforce that.
- Connection tolerance `10 px` (per parent spec). **Decision:** use as
  default; configurable via `ObjectCatalogBuilder.__init__`.
