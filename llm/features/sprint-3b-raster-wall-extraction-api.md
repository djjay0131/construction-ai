# Sprint 3b: Raster Wall Extraction + Parser + API Routing

**Status:** VERIFIED
**Date:** 2026-06-14
**Implemented:** 2026-06-14
**Verified:** 2026-06-14
**Author:** Jason Cusati (with AI assistance)
**Sprint:** 3b of 2 (Sprint 3 — Raster/Scanned Drawing Support)
**Supersedes:** the "wall extraction + scale + parser + API" slice of
`llm/features/sprint-3-raster-scanned-drawing-support.md`. Builds on
Sprint 3a (ImagePreprocessor + CoordinateConverter VERIFIED 2026-06-14).

## Problem

Sprint 3a shipped the two simplest CV modules (skew detection +
pixel→inch translation). To make raster takeoffs actually work end-to-end,
3b adds the wall-extraction algorithm, scale detection, the parser that
wires them together, and the API routing change that drops the
"unsupported file format" raise for JPG/PNG uploads.

## Goals

- **`WallLineExtractor`** uses the existing YOLO detector (via the verified
  model registry from Sprint 0) to find wall regions, then runs
  Canny + HoughLinesP within each wall bounding box. Door/window regions
  suppress overlapping lines. Output: a list of pixel-space segments.
- **`ScaleDetector`** implements a 3-tier cascade with plausibility check:
  1. If the caller provided a `reference_measurement`
     (`{wall_index, length_inches}`), compute scale from that.
  2. Else if the caller provided a `manual_scale` string (e.g.
     `"1/4\"=1'-0\""`), parse it.
  3. Else raise `ScaleWarning` — auto-detect via Gemini Vision / OCR is
     deferred to a follow-up sprint; the warning message names the
     options.
  Plausibility check: every resulting wall must fall in `[2', 80']`.
- **`RasterParser`** orchestrates: load → preprocess → extract → scale →
  convert. Mirrors the `DXFParser` / `PDFParser` interface so
  `app/api/takeoff.py` doesn't need a special-case code path beyond the
  routing.
- **`app/api/takeoff.py`** drops the JPG/PNG rejection and routes to
  `RasterParser`. KG-backed `LumberCalculator` from Sprint 2a consumes
  the output unchanged.
- Tests are unit + mocked-integration. Real images and Gemini/OCR live
  on a follow-up sprint with checked-in test fixtures.
- ≥80% line coverage on new modules. Sprint 2 + 3a regression: zero.

## Non-Goals

- **Real Gemini Vision auto-detect** — deferred. `ScaleDetector` raises
  `ScaleWarning` when neither manual nor reference is given.
- **Real OCR scale-bar reading** — deferred (same reason).
- **Real test-image fixtures (clean_300dpi.png, skewed_*.png, etc.)** —
  deferred. Synthetic numpy arrays + mocked YOLO get us coverage without
  bloating the repo.
- **End-to-end vector-parity check (AC-6 from the parent spec)** —
  needs real fixtures; deferred.
- **Auto-deskew** — never. Standing policy from Sprint 3a.

## Design Approach

### `WallLineExtractor` (`backend/app/core/cv/wall_line_extractor.py`)

```python
class YoloDetector(Protocol):
    """Minimal interface so tests can swap in a fake without importing
    the real DetectionService (which pulls in torch + ultralytics)."""
    def detect(self, image: np.ndarray) -> list[Detection]: ...

@dataclass
class Detection:
    label: str       # "wall" | "door" | "window" | ...
    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2)
    confidence: float

class WallLineExtractor:
    def __init__(self, detector: YoloDetector, padding_px: int = 10): ...
    def extract(self, image: np.ndarray) -> list[PixelSegment]:
        """Return list of ((x1, y1), (x2, y2)) line segments in image-px."""
```

Algorithm:
1. `detector.detect(image)` → list of detections.
2. Split into `wall_boxes` (label == "wall") and `opening_boxes`
   (label in {"door", "window"}).
3. For each wall box:
   a. Crop with `padding_px` extra on each side (clip to image bounds).
   b. Canny edges (50, 150) on the crop.
   c. `cv2.HoughLinesP(edges, 1, π/180, threshold=50, minLineLength=20,
      maxLineGap=10)`.
   d. Translate each line back to full-image coordinates.
   e. Drop lines whose midpoint falls inside any `opening_box`.
4. Return the merged list.

Pairing/merging deferred to a follow-up — single-line-per-wall-region is
sufficient for AC-1 acceptance (BOM is computed from total wall length,
not exact wall count).

### `ScaleDetector` (`backend/app/core/cv/scale_detector.py`)

```python
class ScaleWarning(RuntimeError):
    """Auto-detect couldn't determine a scale and the caller didn't
    provide a manual override or reference measurement. The message
    instructs the caller on how to proceed."""

class ScaleDetector:
    def __init__(
        self,
        min_wall_in: float = 24.0,    # 2 ft
        max_wall_in: float = 960.0,   # 80 ft
    ): ...

    def detect(
        self,
        image: np.ndarray,
        segments_px: list[PixelSegment],
        manual_scale: Optional[str] = None,
        reference: Optional[dict] = None,
    ) -> float:
        """Return pixels-per-inch. Raises ScaleWarning if all tiers fail."""
```

Cascade (first that succeeds wins):
1. **Reference measurement** — if `reference = {"wall_index": N,
   "length_inches": L}`, take the px-length of `segments_px[N]` and
   compute `scale = px_length / L`. Plausibility check after.
2. **Manual scale string** — parse formats like `"1/4\"=1'-0\""` →
   "1/4 inch on paper = 1 foot in reality". With a 96-DPI assumption,
   `scale_px_per_inch = 96 / 48 = 2`. The parse_manual_scale helper
   handles the canonical "N/D"=M'-0\"" formats. Plausibility check after.
3. **Auto-detect** — not yet implemented. Raises `ScaleWarning`.

Plausibility check (applied after tier 1 or 2 succeeds):
- Compute pixel lengths from `segments_px`; convert to inches via
  candidate scale.
- If ANY wall < `min_wall_in` or > `max_wall_in`, raise `ScaleWarning`.

### `RasterParser` (`backend/app/core/parsers/raster_parser.py`)

Orchestrator. Same interface as `DXFParser` / `PDFParser`.

```python
class RasterParseError(RuntimeError):
    """User-facing error from the raster pipeline."""

class RasterParser:
    def __init__(
        self,
        file_path: str | Path,
        detector: YoloDetector | None = None,
        preprocessor: ImagePreprocessor | None = None,
        line_extractor: WallLineExtractor | None = None,
        scale_detector: ScaleDetector | None = None,
    ):
        """All collaborators injectable for tests; defaults wire the real ones."""

    def load(self) -> bool:
        """Read the image from disk. Returns True on success."""

    def extract_walls(
        self,
        manual_scale: Optional[str] = None,
        reference_measurement: Optional[dict] = None,
    ) -> tuple[list[WallElement], dict]:
        """Run the pipeline. Returns (walls, metadata).
        metadata may contain {"scale_warning": "..."} when scale fails.
        """
```

Pipeline:
1. `self.preprocessor.run(self.image)` (raises `SkewRejected` if skewed).
2. `self.line_extractor.extract(cleaned)` → segments_px.
3. If `segments_px` empty: raise `RasterParseError("No walls detected...")`.
4. `self.scale_detector.detect(cleaned, segments_px, manual_scale=...,
   reference=...)` → scale_px_per_in. Catches `ScaleWarning` and returns
   `([], {"scale_warning": message})`.
5. `CoordinateConverter(scale_px_per_in).to_wall_elements(segments_px)` →
   walls. Return `(walls, {})`.

`SkewRejected` is wrapped in `RasterParseError`.

### `app/api/takeoff.py` change

Currently raises `ValueError("Unsupported file format: jpg")` on line 115.
Replace the `else` branch with a new `elif drawing.file_format.value in
['jpg', 'png', 'jpeg']:` branch that constructs a `RasterParser` and calls
`extract_walls`.

Also: accept optional `manual_scale` and `reference_measurement` from
the request body (additive; existing requests still work).

## Sample Implementation

(Real code goes in Phase 4; only the wall-extractor inner loop sketched
here for clarity.)

```python
# Inside WallLineExtractor.extract:
for box in wall_boxes:
    x1, y1, x2, y2 = self._pad_bbox(box.bbox, image.shape, self.padding_px)
    crop = image[y1:y2, x1:x2]
    edges = cv2.Canny(crop, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=50,
                            minLineLength=20, maxLineGap=10)
    if lines is None:
        continue
    for x1l, y1l, x2l, y2l in lines.reshape(-1, 4):
        start = (x1l + x1, y1l + y1)
        end   = (x2l + x1, y2l + y1)
        mid   = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        if any(self._point_in_box(mid, ob.bbox) for ob in opening_boxes):
            continue
        segments.append((start, end))
return segments
```

## Edge Cases & Error Handling

### YOLO returns zero wall detections
- **Scenario:** Image is a photograph or a poor-quality scan.
- **Behavior:** `WallLineExtractor` returns `[]`; `RasterParser` raises
  `RasterParseError("No walls detected in image. Try a clearer scan or
  use the vector pipeline.")`.
- **Test:** Fake detector returns `[]`; expect the error.

### Hough finds no lines in a wall region
- **Scenario:** Wall region is too low-contrast.
- **Behavior:** Skip the region; continue with others. If ALL regions
  produce zero lines, `extract` returns `[]`.
- **Test:** Synthetic image where one wall region is uniform.

### Wall midpoint falls inside a door bbox
- **Scenario:** Door cuts through a wall — line crosses the doorway.
- **Behavior:** Drop the line (the wall terminates at the door edges in
  reality; the line is a YOLO artifact).
- **Test:** Manual line list that has a midpoint inside a fake door bbox.

### Plausibility check kills auto-detected scale
- **Scenario:** Scale would yield a 0.5-ft "wall".
- **Behavior:** `ScaleDetector` raises `ScaleWarning`; `RasterParser`
  returns `([], {"scale_warning": ...})`.
- **Test:** Provide `reference` whose ratio produces an out-of-bounds wall.

### Manual scale string in unparseable format
- **Scenario:** Caller passes `"random text"`.
- **Behavior:** Parser raises `ScaleWarning` with the offending string.
- **Test:** Several invalid strings.

### Reference wall_index out of range
- **Scenario:** `reference["wall_index"]` is 999 but only 3 segments.
- **Behavior:** `ScaleDetector` raises `ScaleWarning` naming the index.
- **Test:** Mismatched index.

### Image fails to load
- **Scenario:** Disk path doesn't exist / corrupt file.
- **Behavior:** `RasterParser.load()` returns `False`. Subsequent
  `extract_walls` raises `RasterParseError`.
- **Test:** Bogus path.

## Acceptance Criteria

### AC-1: Happy path — manual scale produces WallElements
- **Given** a `RasterParser` with mocked collaborators (preprocessor
  returns the input; extractor returns 2 horizontal segments at 100 px
  apart; manual_scale resolves to `scale_px_per_in = 10.0`)
- **When** `extract_walls(manual_scale="...")` is called
- **Then** the return is `(walls, {})` with `len(walls) == 2` and
  `walls[0].length_inches > 0`

### AC-2: Reference measurement overrides everything
- **Given** the same parser and a `reference_measurement={"wall_index":
  0, "length_inches": 120}` where `segments_px[0]` is 600 px long
- **When** `extract_walls(reference_measurement=...)` is called
- **Then** the inferred scale is `600/120 = 5 px/in` and walls are sized
  accordingly

### AC-3: Both null → ScaleWarning bubbles as metadata
- **Given** a parser whose extractor returns non-empty segments and a
  call without `manual_scale` or `reference_measurement`
- **When** `extract_walls()` is called
- **Then** the return is `([], {"scale_warning": "<message>"})` and the
  message names both override options

### AC-4: Skewed image rejected via wrapped exception
- **Given** a parser whose preprocessor raises `SkewRejected`
- **When** `extract_walls()` is called
- **Then** `RasterParseError` is raised with the skew angle in the message

### AC-5: No walls detected → RasterParseError
- **Given** a parser whose extractor returns `[]`
- **When** `extract_walls()` is called
- **Then** `RasterParseError` is raised mentioning "no walls"

### AC-6: Wall-line extractor suppresses lines inside opening boxes
- **Given** a fake detector that returns one wall bbox covering the
  whole image AND one door bbox covering its center, and a synthetic
  image with edges
- **When** `WallLineExtractor.extract(image)` is called
- **Then** every returned segment has a midpoint outside the door bbox

### AC-7: Manual scale parser accepts canonical formats
- **Given** strings: `"1/4\"=1'-0\""`, `"1/8\"=1'-0\""`, `"1\"=1'-0\""`
- **When** parsed via the helper
- **Then** each returns a positive scale; obviously invalid strings
  raise `ScaleWarning`

### AC-8: Plausibility check vetoes ridiculous scale
- **Given** scale that would render a 0.5-ft wall
- **When** `ScaleDetector.detect(...)` returns
- **Then** `ScaleWarning` is raised

### AC-9: API routes JPG/PNG to RasterParser
- **Given** a drawing with `file_format = jpg`
- **When** the takeoff endpoint runs
- **Then** the request is routed to `RasterParser` (not the rejection
  branch); existing DXF / PDF paths untouched

### AC-10: Coverage + regression
- **Given** the implementation is complete
- **When** `pytest tests/test_wall_line_extractor.py
  tests/test_scale_detector.py tests/test_raster_parser.py
  --cov=app.core.cv.wall_line_extractor
  --cov=app.core.cv.scale_detector
  --cov=app.core.parsers.raster_parser` is run
- **Then** coverage is ≥80% on each new module
- **And** the 74 Sprint 2 + 3a tests still pass

## Technical Notes

- **Affected files:**
  - `backend/app/core/cv/wall_line_extractor.py` (new)
  - `backend/app/core/cv/scale_detector.py` (new)
  - `backend/app/core/parsers/raster_parser.py` (new)
  - `backend/app/api/takeoff.py` (small edit: route JPG/PNG branch)
  - `backend/tests/test_wall_line_extractor.py` (new)
  - `backend/tests/test_scale_detector.py` (new)
  - `backend/tests/test_raster_parser.py` (new)
  - `.github/workflows/ci.yml` (add the three new test files + cov targets)
- **No new runtime deps.** `opencv-python` is already in requirements;
  YOLO/ultralytics + easyocr are already in requirements (Gemini/OCR
  call paths are NOT exercised by Sprint 3b).
- **Test strategy:** all new modules use Protocol-based dependency
  injection so tests can pass in fakes. No torch, no ultralytics, no
  easyocr loaded at test time.

## Dependencies

- Sprint 3a VERIFIED (`ImagePreprocessor` + `CoordinateConverter`).
- Sprint 2a VERIFIED (KG-backed `LumberCalculator` consumes `WallElement[]`).

## Open Questions

- Should the route grow `--reference-measurement` and `--manual-scale`
  query/body params now or in a follow-up? **Decision:** add them as
  optional fields on the existing request body (additive).
- Should the API surface the `scale_warning` to the caller? **Decision:**
  yes — when the parser returns `(_, {"scale_warning": msg})`, the takeoff
  response includes `scale_warning` at the top level alongside the
  (empty) materials list.
