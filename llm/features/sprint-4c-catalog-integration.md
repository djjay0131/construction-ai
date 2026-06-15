# Sprint 4c: Catalog Integration (EasyOcrReader + Raster Wiring + Catalog API)

**Status:** IMPLEMENTED
**Date:** 2026-06-14
**Implemented:** 2026-06-14
**Author:** Jason Cusati (with AI assistance)
**Sprint:** 4c of 3 (Sprint 4 — OCR Dimension Extraction & Object Catalog)
**Depends on:** Sprint 4a VERIFIED + Sprint 4b VERIFIED.

## Problem

Sprint 4a + 4b built every piece of the OCR + catalog pipeline in
isolation, all at 100% coverage with synthetic inputs. But none of it
is wired into the live backend — the `RasterParser` doesn't yet
build a catalog, the takeoff response doesn't surface OCR validation
results, there's no API for retrieving a catalog, and there's no real
`OcrReader` that wraps EasyOCR (Sprint 4a kept it as a Protocol).

This sprint takes the last-mile step: the raster takeoff path uses
EasyOCR for real, persists a catalog file per takeoff, surfaces
validation flags in `MaterialTakeoff.notes`, and exposes the catalog
via a new `GET /api/catalog/{takeoff_id}` endpoint.

## Goals

- `EasyOcrReader` wraps `easyocr.Reader` to satisfy the Sprint 4a
  `OcrReader` Protocol. Lazy initialisation — the ~200 MB model only
  downloads when `readtext()` is actually called the first time, not at
  module import.
- `RasterParser.extract_walls()` (extended) optionally produces a
  catalog alongside the walls. The takeoff API constructs the full
  CV + OCR + catalog pipeline once and persists results to a
  per-takeoff path.
- `app/api/takeoff.py` for JPG/PNG: build + persist catalog; include
  validation summary in `MaterialTakeoff.notes`.
- New `GET /api/catalog/{takeoff_id}` endpoint returns the persisted
  catalog JSON. 404 when no catalog exists for that takeoff.
- ≥80% line coverage on new modules; zero regression in the 226
  Sprint 2/3/4a/4b tests.

## Non-Goals

- **End-to-end vector-parity check** with real plan-set fixtures —
  parent Sprint 3 AC-6 stays deferred (needs checked-in PNG/DXF
  pairs). Sprint 4c covers wiring; 5 covers fixture-driven validation.
- **Real Gemini Vision auto-detect** in `ScaleDetector` — still a
  Sprint-3-Open follow-up. Caller still provides `manual_scale` or
  `reference_measurement`.
- **NetworkX backend for `CatalogStore`** — parent's "Storage Format
  Experiment" still defers; stay with `JsonCatalogStore`.
- **Catalog versioning** — overwrite-on-save is fine for v1.
- **Real EasyOCR model download in CI** — we mock the reader at the
  unit-test boundary; CI doesn't pull 200 MB.

## Design Approach

### `EasyOcrReader` (`backend/app/core/cv/easyocr_reader.py`)

```python
class EasyOcrReader:
    """OcrReader implementation backed by EasyOCR. Lazy reader init."""

    def __init__(self, languages: list[str] | None = None, gpu: bool = False): ...

    def readtext(self, image) -> list[TextBox]: ...
```

EasyOCR's `Reader.readtext()` returns
`[(quad_points, text, confidence), ...]` where `quad_points` is a
4-point polygon. We collapse it to an axis-aligned bbox via min/max.

Lazy init: the `easyocr.Reader(...)` constructor downloads ~200 MB on
first use. To keep import-time fast and tests mockable, the reader is
created on first `readtext()` call, not in `__init__`.

### Per-takeoff catalog persistence

Catalog files live next to the takeoff's source image under
``{UPLOAD_DIR}/analysis/{takeoff_id}/catalog.json``. The takeoff API
ensures the directory exists, writes via `CatalogStore.save()`, and
records the path in `MaterialTakeoff.notes`.

### `app/api/catalog.py` — `GET /api/catalog/{takeoff_id}`

```python
@router.get("/{takeoff_id}")
def get_catalog(takeoff_id: int) -> dict:
    """Return the persisted catalog JSON for a takeoff.
    404 if the takeoff doesn't have one."""
```

Resolves the takeoff record (so we can return 404 if the id doesn't
exist), then constructs the catalog path. If the file doesn't exist
→ 404 with a message naming the takeoff_id.

Wired in `main.py` with `app.include_router(catalog.router,
prefix="/api/catalog", tags=["Catalog"])`.

### Takeoff pipeline glue (in `process_drawing_takeoff`)

JPG/PNG branch becomes (paraphrased):

```python
from app.core.cv.dimension_extractor import DimensionExtractor
from app.core.cv.easyocr_reader import EasyOcrReader
from app.core.catalog.catalog_builder import ObjectCatalogBuilder
from app.core.catalog.catalog_store import CatalogStore

# 1. Walls (existing Sprint 3b path)
walls = raster_parser.extract_walls(manual_scale=..., reference_measurement=...)

# 2. OCR dimensions
extractor = DimensionExtractor(reader=EasyOcrReader())
parsed_dims, _ = extractor.extract(raster_parser.image)

# 3. Catalog
builder = ObjectCatalogBuilder()
catalog = builder.build(
    wall_segments=raster_parser.last_wall_segments(),
    detections=raster_parser.last_detections(),
    dimensions=parsed_dims,
    scale_px_per_in=raster_parser.last_scale_px_per_in(),
)

# 4. Persist
catalog_path = settings.UPLOAD_DIR / "analysis" / str(takeoff_id) / "catalog.json"
CatalogStore().save(catalog, catalog_path)

# 5. Validation summary into takeoff.notes
summary = summarise_validation(catalog)  # counts confirmed / discrepancy / mismatch
takeoff_record.notes = (takeoff_record.notes or "") + f"\nCatalog: {summary}"
```

`raster_parser.last_wall_segments()` and friends require `RasterParser`
to record state during `extract_walls()`. **Better:** restructure
`RasterParser.extract_walls()` to optionally accept an
`ObjectCatalogBuilder` and return `(walls, metadata, catalog)`. That
keeps the caller simple and Sprint 4c-friendly.

```python
def extract_walls(
    self,
    manual_scale=None,
    reference_measurement=None,
    catalog_builder: ObjectCatalogBuilder | None = None,
    dimensions: Sequence[ParsedDimension] | None = None,
) -> tuple[list[WallElement], dict, Catalog | None]:
    ...
```

If both `catalog_builder` and `dimensions` are provided, the parser
builds a catalog from the same pipeline state and returns it. Backward
compatible: omit → returns `(walls, metadata, None)`.

### Validation summary helper (`app/core/catalog/validation_summary.py`)

```python
@dataclass(frozen=True)
class ValidationSummary:
    walls_total: int
    walls_confirmed: int
    walls_minor_discrepancy: int
    walls_mismatch: int

def summarise_validation(catalog: Catalog) -> ValidationSummary: ...
```

Tiny pure-data helper so the takeoff API doesn't recompute it inline.

## Edge Cases & Error Handling

### EasyOCR model not yet downloaded
- **Scenario:** First call on a fresh image — easyocr downloads ~200 MB.
- **Behavior:** First `readtext()` call may take 30–60 s. Log a one-time
  notice on first init.
- **Test:** `EasyOcrReader.__init__` mocked; assert `_reader` lazily
  populated.

### No catalog for the requested takeoff
- **Scenario:** `GET /api/catalog/{takeoff_id}` where the file doesn't exist.
- **Behavior:** Return 404 with `{"detail": "..."}`.
- **Test:** Yes.

### Takeoff id doesn't exist at all
- **Scenario:** `GET /api/catalog/999999`
- **Behavior:** Return 404 with message naming the id.
- **Test:** Yes.

### Catalog file is corrupt
- **Scenario:** JSON file exists but `JSONDecodeError`.
- **Behavior:** Return 500 with a clear message (don't crash the worker).
- **Test:** Write garbage, hit endpoint.

### Catalog persists across reprocesses
- **Scenario:** Reprocess the same takeoff — overwrite-on-save (v1).
- **Behavior:** New `save()` overwrites; no archive of the previous.
- **Test:** Two saves; load returns the second.

### Quad-points convert correctly to bbox
- **Scenario:** EasyOCR returns `[[10, 5], [60, 5], [60, 25], [10, 25]]`
  (axis-aligned rectangle).
- **Behavior:** `(10, 5, 60, 25)`.
- **Test:** With both axis-aligned and slightly-rotated quads.

## Acceptance Criteria

### AC-1: EasyOcrReader satisfies OcrReader Protocol
- **Given** an `EasyOcrReader()` instance with a fake `easyocr` module
  patched in
- **When** `DimensionExtractor(reader=EasyOcrReader()).extract(image)`
  is called
- **Then** it returns the `(parsed_dimensions, raw_texts)` tuple shape
  identical to the Sprint 4a contract

### AC-2: Lazy reader initialization
- **Given** `EasyOcrReader()` is constructed
- **When** the constructor returns
- **Then** the underlying `easyocr.Reader` has NOT been instantiated yet

### AC-3: Lazy init triggers on first readtext
- **Given** the same constructed reader
- **When** `readtext(image)` is called for the first time
- **Then** the `easyocr.Reader` is instantiated exactly once;
  subsequent `readtext()` calls reuse the same instance

### AC-4: Quad-points → axis-aligned bbox
- **Given** EasyOCR returns `[(quad, text, confidence)]` with
  `quad = [[10, 5], [60, 5], [60, 25], [10, 25]]`
- **When** the reader's adapter runs
- **Then** the resulting `TextBox.bbox` is `(10, 5, 60, 25)`

### AC-5: RasterParser builds catalog when builder is provided
- **Given** a `RasterParser` and an `ObjectCatalogBuilder`
- **When** `extract_walls(catalog_builder=..., dimensions=[...])` is called
- **Then** the third return value is a populated `Catalog`; if either
  is omitted, the third return is `None`

### AC-6: Catalog persistence path is per-takeoff
- **Given** a takeoff id and `UPLOAD_DIR`
- **When** the takeoff API runs the JPG/PNG branch
- **Then** the catalog is saved at
  `{UPLOAD_DIR}/analysis/{takeoff_id}/catalog.json`

### AC-7: GET /api/catalog/{id} returns the saved JSON
- **Given** a catalog has been saved for takeoff 42
- **When** `GET /api/catalog/42` is called
- **Then** the response body equals the JSON written by
  `CatalogStore.save()`

### AC-8: GET /api/catalog/{id} 404s when missing
- **Given** no catalog file at the expected path
- **When** the endpoint is called
- **Then** status code is 404 and detail names the takeoff id

### AC-9: Validation summary counts buckets
- **Given** a catalog with 1 confirmed wall, 1 minor_discrepancy, and
  1 mismatch
- **When** `summarise_validation(catalog)` is called
- **Then** the returned `ValidationSummary` has the right counts

### AC-10: ≥80% coverage + Sprint 2/3/4a/4b regression
- **Given** the implementation is complete
- **When** the new tests run with coverage
- **Then** ≥80% on each new module
- **And** the 226 Sprint 2/3/4a/4b tests still pass

## Technical Notes

- **Affected files:**
  - `backend/app/core/cv/easyocr_reader.py` (new)
  - `backend/app/core/catalog/validation_summary.py` (new)
  - `backend/app/api/catalog.py` (new)
  - `backend/app/core/parsers/raster_parser.py` — extend `extract_walls`
    to optionally accept `catalog_builder` + `dimensions`
  - `backend/app/api/takeoff.py` — JPG/PNG branch wires the full
    pipeline + persists catalog + updates `notes`
  - `backend/app/main.py` — include the new catalog router
  - `backend/tests/test_easyocr_reader.py` (new)
  - `backend/tests/test_validation_summary.py` (new)
  - `backend/tests/test_catalog_endpoint.py` (new)
  - `backend/tests/test_raster_parser.py` — extend with the new
    catalog-emit path
  - `.github/workflows/ci.yml` — add the 3 new test files +
    cov targets
- **No new runtime dependencies.** `easyocr` is already in
  `requirements.txt`; networkx still NOT added.

## Dependencies

- Sprint 3b VERIFIED (RasterParser foundation we extend).
- Sprint 4a VERIFIED (Protocol + DimensionExtractor consumed unchanged).
- Sprint 4b VERIFIED (ObjectCatalogBuilder + CatalogStore consumed unchanged).

## Open Questions

- Should the catalog endpoint require auth? **Decision:** no in 4c —
  the live deployment doesn't have auth yet (backlog 10.5); endpoint
  is publicly invokable like the takeoff API.
- Should we lazy-import easyocr in the reader to keep test imports
  cheap? **Decision:** yes — `import easyocr` happens inside
  `_get_reader()`, not at module top. Tests can patch the import
  cleanly.
- Should takeoff failure persist a partial catalog? **Decision:** no —
  only persist on the happy path. Partial catalogs would confuse
  consumers.
