# Sprint 4d: Takeoff Wiring (Raster + OCR + Catalog End-to-End)

**Status:** IMPLEMENTED
**Date:** 2026-06-14
**Implemented:** 2026-06-14
**Author:** Jason Cusati (with AI assistance)
**Sprint:** 4d of 4 (Sprint 4 — final wiring)
**Depends on:** Sprint 4c VERIFIED.

## Problem

Sprint 4c shipped every module the catalog needs (EasyOcrReader, raster
parser extension, validation summary, API endpoint) at 100% coverage,
but they're not yet stitched together in the takeoff API. A JPG/PNG
upload still produces a wall-only takeoff with no catalog persisted,
no OCR validation, and no `validation_summary` in `MaterialTakeoff.notes`.

This sprint resolves the chicken-and-egg — the catalog needs YOLO
detections (for door/window/opening nodes), but they're computed
inside `extract_walls` — by having `WallLineExtractor` cache its
last-run detections, and `RasterParser.extract_walls` fall back to
them when the caller doesn't pass any. The takeoff API then calls a
new `raster_takeoff` helper that runs the whole chain.

## Goals

- `WallLineExtractor` exposes `last_detections` populated during
  `extract()`. (Tiny, additive state — fine because the extractor is
  per-request scope in the takeoff path.)
- `RasterParser.extract_walls(catalog_builder=..., dimensions=...,
  detections=None)` falls back to `line_extractor.last_detections`
  when ``detections`` is None.
- New `app/core/raster_takeoff.py` with
  `run_raster_takeoff_with_catalog(...)` that:
  1. Constructs `DimensionExtractor` (with injected OCR reader),
  2. Runs it on the loaded image to get parsed dimensions,
  3. Calls `RasterParser.extract_walls(catalog_builder=..., dimensions=...)`,
  4. Persists the catalog under
     `{UPLOAD_DIR}/analysis/{takeoff_id}/catalog.json`,
  5. Returns `(walls, metadata, summary, catalog_path)`.
- `app/api/takeoff.py` JPG/PNG branch calls `run_raster_takeoff_with_catalog`,
  appends the summary to `MaterialTakeoff.notes`.
- ≥80% line coverage on `raster_takeoff` + `WallLineExtractor.last_detections`
  changes; zero regression in the 251 Sprint 2/3/4a/4b/4c tests.

## Non-Goals

- **Live end-to-end smoke against the deployed URL with a real
  raster image** — out of scope; needs a real fixture committed to the
  repo. Defer to a follow-up that ships the fixture too.
- **Updating the smoke_test.py CLI** — current smoke tests
  `kg_status=ready`; the raster takeoff doesn't change that.
- **Real Gemini Vision auto-detect** — still a separate follow-up.
- **takeoff.py full unit test** — the existing function does heavy DB
  + file I/O; mocking all of that is out of scope. Test the
  `raster_takeoff` helper instead, then wire the call site with a
  comment.

## Design Approach

### `WallLineExtractor.last_detections`

```python
class WallLineExtractor:
    def __init__(self, detector, ...):
        ...
        self.last_detections: list[Detection] = []

    def extract(self, image):
        if image is None or getattr(image, "size", 0) == 0:
            raise ValueError(...)
        detections = self.detector.detect(image)
        self.last_detections = detections   # cache for the catalog builder
        ...
```

Stateful, but the extractor is per-request scope — the takeoff API
constructs a fresh one each call.

### `RasterParser.extract_walls` fallback

```python
if catalog_builder is not None and dimensions is not None:
    effective_dets = (
        detections if detections is not None
        else getattr(self.line_extractor, "last_detections", [])
    )
    catalog = catalog_builder.build(
        wall_segments=segments_px,
        detections=effective_dets,
        dimensions=dimensions,
        scale_px_per_in=scale_px_per_in,
    )
```

### `app/core/raster_takeoff.py`

```python
@dataclass(frozen=True)
class RasterTakeoffResult:
    walls: list[WallElement]
    metadata: dict
    summary: ValidationSummary | None
    catalog_path: str | None  # relative to UPLOAD_DIR

def run_raster_takeoff_with_catalog(
    raster_parser: RasterParser,
    ocr_reader: OcrReader,
    *,
    takeoff_id: int,
    upload_dir: str | Path,
    manual_scale: str | None = None,
    reference_measurement: dict | None = None,
    catalog_builder: ObjectCatalogBuilder | None = None,
) -> RasterTakeoffResult: ...
```

Behavior:
1. `raster_parser.load()` if needed — fail fast if it returns False.
2. Build a `DimensionExtractor(reader=ocr_reader)` and run on
   `raster_parser.image`.
3. Call `raster_parser.extract_walls(...)` with the catalog builder
   and parsed dimensions. Receives `(walls, meta, catalog)`.
4. If `catalog is None` (scale warning, etc.), return the result
   without persisting.
5. If `catalog` is populated, save via `CatalogStore` to
   `{upload_dir}/analysis/{takeoff_id}/catalog.json`. Compute
   `summarise_validation(catalog)`. Return everything.

### Test strategy

Helper module is unit-testable with the same FakeReader pattern from
Sprint 4c + a stub RasterParser. No DB, no easyocr, no torch.

### `app/api/takeoff.py` JPG/PNG branch (final shape)

```python
elif drawing.file_format.value in ['jpg', 'png', 'jpeg']:
    from app.core.cv.detection_service import get_detection_service
    from app.core.cv.easyocr_reader import EasyOcrReader
    from app.core.cv.wall_line_extractor import WallLineExtractor
    from app.core.catalog.catalog_builder import ObjectCatalogBuilder
    from app.core.raster_takeoff import run_raster_takeoff_with_catalog

    line_extractor = WallLineExtractor(detector=get_detection_service())
    raster_parser = RasterParser(drawing.file_path, line_extractor=line_extractor)

    if not raster_parser.load():
        raise Exception(f"Failed to load {drawing.file_format.value.upper()} image...")

    try:
        result = run_raster_takeoff_with_catalog(
            raster_parser,
            ocr_reader=EasyOcrReader(),
            takeoff_id=takeoff_record.id,
            upload_dir=settings.UPLOAD_DIR,
            manual_scale=manual_scale,
            reference_measurement=reference_measurement,
            catalog_builder=ObjectCatalogBuilder(),
        )
    except RasterParseError as exc:
        raise Exception(str(exc)) from exc

    walls = result.walls
    if result.summary is not None:
        catalog_note = f"\nRaster catalog: {result.summary} (saved to {result.catalog_path})"
        takeoff_record.notes = (takeoff_record.notes or "") + catalog_note

    if result.metadata.get("scale_warning"):
        logger.warning(f"Raster scale detection: {result.metadata['scale_warning']}")
```

## Acceptance Criteria

### AC-1: `WallLineExtractor.last_detections` populated by extract
- **Given** a `WallLineExtractor` with a fake detector
- **When** `extract(image)` is called
- **Then** `last_detections` matches what the detector returned

### AC-2: `last_detections` starts empty
- **Given** a freshly-constructed `WallLineExtractor`
- **When** no `extract()` call has been made
- **Then** `last_detections == []`

### AC-3: Parser falls back to last_detections
- **Given** a parser whose line extractor cached detections during the
  Sprint 3b wall extraction, and a builder + dimensions but
  `detections=None`
- **When** `extract_walls(...)` is called
- **Then** the catalog is built using `line_extractor.last_detections`

### AC-4: Explicit detections override last_detections
- **Given** the same setup but with explicit `detections=[...]` passed
- **When** `extract_walls(...)` is called
- **Then** the catalog is built using the explicit list

### AC-5: `run_raster_takeoff_with_catalog` happy path
- **Given** a stub RasterParser, a fake OCR reader, and a real
  ObjectCatalogBuilder
- **When** the helper runs
- **Then** the returned `walls` matches the parser's output, the
  catalog file exists at the expected path, `summary` is a
  `ValidationSummary`, and `catalog_path` matches

### AC-6: Helper persists at `{upload_dir}/analysis/{takeoff_id}/catalog.json`
- **Given** `takeoff_id=42`, `upload_dir=tmp_path`
- **When** the helper succeeds
- **Then** the catalog exists at `tmp_path/analysis/42/catalog.json`

### AC-7: Scale warning → no persistence
- **Given** a parser whose `extract_walls` returns `(., scale_warning, None)`
- **When** the helper runs
- **Then** no catalog file is written; `summary` is None;
  `catalog_path` is None

### AC-8: Helper auto-loads when parser.image is None
- **Given** a parser that hasn't been `.load()`-ed yet
- **When** the helper runs
- **Then** it calls `parser.load()` and proceeds

### AC-9: Helper raises when parser.load() fails
- **Given** a parser whose loader returns False
- **When** the helper runs
- **Then** a `RasterParseError` is raised

### AC-10: ≥80% coverage + regression
- **Given** the implementation is complete
- **When** the new tests run with coverage
- **Then** coverage is ≥80% on `raster_takeoff` + the
  `last_detections` lines in `wall_line_extractor`
- **And** the 251 prior Sprint 2/3/4a/4b/4c tests still pass

## Technical Notes

- **Affected files:**
  - `backend/app/core/cv/wall_line_extractor.py` — add
    `last_detections` attribute + tests
  - `backend/app/core/parsers/raster_parser.py` — fall back when
    `detections=None`
  - `backend/app/core/raster_takeoff.py` (new)
  - `backend/app/api/takeoff.py` — call the helper from the JPG/PNG branch
  - `backend/tests/test_wall_line_extractor.py` — extend
  - `backend/tests/test_raster_parser.py` — extend
  - `backend/tests/test_raster_takeoff.py` (new)
  - `.github/workflows/ci.yml` — add the new test file + cov target

## Dependencies

- Sprint 4c VERIFIED.

## Open Questions

- Should the helper return the catalog itself (in memory)?
  **Decision:** no — the summary is what consumers need; the catalog
  is served via `/api/catalog/{id}` from disk. Keeps the return type
  small.
