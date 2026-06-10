# Sprint 3: Raster/Scanned Drawing Support

**Status:** SPECIFIED
**Date:** 2026-06-10
**Author:** Jason Cusati (with AI assistance)
**Sprint:** 3 of 5 (2026 Product Roadmap)
**Supersedes:** `llm/features/raster-scanned-drawing-support.md` (2026-04-01) —
the original spec predates Sprint 2's GCP deploy + KG-backed lumber dict;
this revision reuses its architecture and ACs but pins terminology and
non-goals to the current execution path.

## Problem

Users with scanned or photographed construction drawings (JPG, PNG) cannot
run material takeoffs because the takeoff pipeline only handles vector
formats (DXF/DWG/PDF). The upload API already accepts image files and
parallel CV infrastructure exists (`backend/app/core/cv/`, YOLO model
registry verified 2026-04-03), but there is no conversion path from pixel
data to the `WallElement[]` geometry that `LumberCalculator` requires.

This blocks a class of users — contractors with paper plans, archives of
older drawings, or field workers photographing plans on site. Sprint 3 adds
the missing pipeline and wires it into the takeoff API behind the existing
upload flow.

## Goals

- **Full material takeoff parity** with the vector pipeline: a JPG/PNG
  upload produces the same `MaterialTakeoff` shape (studs, plates, lumber
  list) as a DXF/PDF upload.
- **Automatic scale detection** from title blocks, scale bars, or dimension
  annotations. Cascade: Gemini Vision → EasyOCR → manual fallback. Each
  result runs through a residential-bounds plausibility check.
- **Skewed-drawing rejection** (>5°) with a clear, actionable error
  message. The system never silently corrects skew — the spec's explicit
  decision (per `reference_pages_mirror`-style design choices: skewed
  drawings are out of scope and rejected, not corrected).
- **Accuracy target:** raster takeoff wall count and linear footage within
  10% of the vector takeoff on the same drawing.
- **Pipeline integration:** the new `RasterParser` slots into the existing
  routing in `app/api/takeoff.py` without breaking any DXF/PDF path.
- **YOLO model sourcing:** use the existing model registry (`app/core/ml/`)
  to fetch the active "Wall" detection model. No re-training is in scope.
- **KG-backed lumber dict:** the calculator continues to use the
  Sprint 2a-loaded `lumber_specs` dict; raster output flows into it
  unchanged.

## Non-Goals

- **Training a custom YOLO model.** Out of scope; depends on backlog 2.1.
  This sprint uses the pre-trained model already in the registry.
- **Robustness to heavily degraded scans** (severe shadows, creases, low
  contrast, JPEG compression artifacts). Target clean-to-moderate quality
  scans (300+ DPI, minimal noise). Degraded handling is a follow-up.
- **Multi-page raster** (backlog 1.6).
- **3D / isometric / handwritten / floor-plan-from-photo-of-built-structure
  interpretation.** Each is a separate research problem.
- **Skew correction.** Drawings are rejected when skewed >5°; no
  deskew step is added (per the project's standing policy from earlier
  specs).
- **OCR dimension validation** is OCR's job — Sprint 4 (already SPECIFIED
  at `ocr-dimension-extraction.md`). Sprint 3 uses OCR only inside
  `ScaleDetector`'s cascade for scale-bar reads.

## User Stories

- As a contractor, I want to upload a scanned floor plan image and get a
  full material takeoff, so I can generate lumber lists from paper drawings.
- As a project manager, I want the system to auto-detect drawing scale from
  the scanned plan, so I don't have to manually calculate pixel-to-inch ratios.
- As a field worker, I want to photograph a drawing on site and get an
  estimate, so I can verify quantities without returning to the office.
- As an integrator, I want the raster pipeline to plug into the existing
  ``POST /api/takeoff/process/{drawing_id}`` endpoint, so client code
  doesn't need to know the upload was raster vs vector.

## Design Approach

### Architecture

```
JPG/PNG upload  →  TakeoffAPI routing on DrawingFormat
                    │
                    ▼
              RasterParser
                ├── ImagePreprocessor
                │     ├── Skew detection (Hough dominant-angle)
                │     ├── Reject if |skew| > 5°
                │     ├── CLAHE contrast enhancement
                │     └── Gaussian denoise + adaptive threshold
                ├── YOLO Object Detection (via model registry)
                │     └── Returns {Wall, Door, Window, Column} bboxes
                ├── WallLineExtractor (YOLO-constrained Hough)
                │     ├── Per Wall bbox: crop + pad
                │     ├── Canny edges → morphological closing
                │     ├── Probabilistic Hough line transform
                │     ├── Suppress lines inside Door/Window bboxes
                │     ├── Map line coords back to full image
                │     ├── Parallel-line pairing → wall thickness
                │     └── Collinear segment merging across regions
                ├── ScaleDetector (cascade with plausibility check)
                │     ├── 1. Gemini Vision (title block analysis)
                │     ├── 2. EasyOCR (scale bar / dimension annotation)
                │     ├── 3. Manual override (user-provided)
                │     └── Plausibility: every wall in [2', 80'],
                │         total footprint < 20,000 sqft
                │         → return scale_warning if fails
                └── CoordinateConverter (pixels → inches → WallElement[])
                    │
                    ▼
            LumberCalculator (Sprint 2a, KG-backed) — unchanged
                    │
                    ▼
              MaterialTakeoff response
```

### Key Components (all new under `backend/app/core/`)

1. **`parsers/raster_parser.py`** — `RasterParser` class mirroring the
   `PDFParser` / `DXFParser` interface. Orchestrates the pipeline.
2. **`cv/image_preprocessor.py`** — `ImagePreprocessor`. Hough dominant
   angle skew detection (reject if >5°); CLAHE; Gaussian denoise;
   adaptive threshold.
3. **`cv/wall_line_extractor.py`** — `WallLineExtractor`. YOLO-constrained
   Hough line extraction per wall region; door/window suppression;
   parallel-line pairing; segment merging.
4. **`cv/scale_detector.py`** — `ScaleDetector`. Cascade with plausibility
   check returning either a numeric scale (pixels-per-inch) or a
   ``scale_warning`` describing why detection failed / suggesting manual
   reference.
5. **`cv/coordinate_converter.py`** — `CoordinateConverter`. Pure-function
   helpers: ``pixels_to_inches``, ``rasterize_wall_polylines``.

### Pipeline integration

In ``app/api/takeoff.py``, the current logic raises for image formats
(file_format = JPG/PNG/JPEG). Replace that raise with a route:

```python
if drawing.file_format == DrawingFormat.JPG or drawing.file_format == DrawingFormat.PNG:
    parser = RasterParser(file_path)
    parser.load()
    walls = parser.extract_walls(
        manual_scale=request.manual_scale,           # optional, default None
        reference_measurement=request.reference_measurement,  # optional, default None
    )
elif drawing.file_format == DrawingFormat.DXF:
    walls = DXFParser(file_path).parse()
elif drawing.file_format == DrawingFormat.PDF:
    walls = PDFParser(file_path).parse()
```

The KG-backed ``LumberCalculator`` from Sprint 2a consumes ``walls``
unchanged.

### Reference-measurement override

If ``ScaleDetector`` returns ``scale_warning``, the takeoff response
includes that flag and an empty / partial result; client may then re-call
the endpoint with ``reference_measurement={wall_index: N, length_inches: L}``
to override the scale and regenerate. Implementation: in
``RasterParser.extract_walls``, if ``reference_measurement`` is provided,
compute scale from it (``length_inches / measured_pixels(wall_index)``)
before the regular cascade.

### Test images and fixtures

Test fixtures live under ``backend/tests/fixtures/raster/``:
- ``clean_300dpi_scaled.png`` — clean scan, visible scale bar, no skew.
- ``skewed_7deg.png`` — same scan rotated 7° (must be rejected).
- ``skewed_3deg.png`` — same scan rotated 3° (must be accepted).
- ``low_dpi_72.png`` — downsampled to 72 DPI (must fail gracefully).
- ``no_scale_annotation.png`` — no detectable scale (must enter manual
  override path).
- ``photo_of_room.jpg`` — not a floor plan (must be rejected without crash).

Each fixture should be small (<200 KB) so the repo doesn't bloat. If a
public test corpus exists (e.g., CubiCasa5K), reference its URL and skip
checking the images in.

### YOLO model registry integration

``WallLineExtractor`` and ``RasterParser`` call
``app.core.ml.model_registry.get_model_registry()`` to fetch the active
"floorplan-objects" model (already in registry; loaded from
``gs://construction-ai-models/``). No new registry entries needed.
``ALLOW_YOLO_MOCK`` env var (default false) lets tests substitute a fake
detector.

## Sample Implementation

```python
# === backend/app/core/parsers/raster_parser.py (core flow) ===
from pathlib import Path
from typing import Optional

import cv2

from app.core.cv.coordinate_converter import CoordinateConverter
from app.core.cv.image_preprocessor import ImagePreprocessor, SkewRejected
from app.core.cv.scale_detector import ScaleDetector, ScaleWarning
from app.core.cv.wall_line_extractor import WallLineExtractor
from app.core.ml.model_registry import get_model_registry
from app.core.parsers.dxf_parser import WallElement


class RasterParseError(RuntimeError):
    """Top-level error from the raster pipeline (message is user-facing)."""


class RasterParser:
    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self.image = None
        self.preprocessor = ImagePreprocessor()
        self.line_extractor = WallLineExtractor(model_registry=get_model_registry())
        self.scale_detector = ScaleDetector()

    def load(self) -> bool:
        self.image = cv2.imread(str(self.file_path))
        return self.image is not None

    def extract_walls(
        self,
        manual_scale: Optional[str] = None,
        reference_measurement: Optional[dict] = None,
    ) -> tuple[list[WallElement], dict]:
        """Return (walls, metadata). metadata may contain scale_warning."""
        if self.image is None and not self.load():
            raise RasterParseError(f"Could not load image {self.file_path}")

        try:
            cleaned = self.preprocessor.run(self.image)
        except SkewRejected as exc:
            raise RasterParseError(str(exc)) from exc

        wall_segments_px = self.line_extractor.extract(cleaned, self.file_path)
        if not wall_segments_px:
            raise RasterParseError(
                "No walls detected in image. Try a clearer scan or use the vector pipeline."
            )

        try:
            scale_px_per_in = self.scale_detector.detect(
                cleaned, manual_scale=manual_scale,
                wall_segments_px=wall_segments_px,
                reference=reference_measurement,
            )
        except ScaleWarning as warn:
            return [], {"scale_warning": warn.message}

        converter = CoordinateConverter(scale_px_per_in)
        walls = converter.to_wall_elements(wall_segments_px)
        return walls, {}
```

## Edge Cases & Error Handling

(Same set as the 2026-04-01 spec; reproduced here for the contract.)

### Skewed image
- **Scenario:** Image rotated > 5°.
- **Behavior:** ``ImagePreprocessor.detect_skew`` raises ``SkewRejected``
  with the measured angle in the message; ``RasterParseError`` propagates.
- **Test:** Rotate the clean fixture by 3° (pass), 5°, 10° (reject); assert
  angle appears in error message.

### No wall regions detected
- **Scenario:** YOLO returns zero "Wall" boxes (e.g., photograph of a room).
- **Behavior:** ``RasterParseError("No walls detected in image...")``.
- **Test:** ``photo_of_room.jpg`` fixture.

### No scale detected and no manual override
- **Scenario:** All three cascade tiers fail.
- **Behavior:** Return ``([], {"scale_warning": "..."})``.
- **Test:** ``no_scale_annotation.png``.

### Low-DPI / blurry
- **Scenario:** <150 DPI or significant blur — Hough finds <3 segments.
- **Behavior:** ``RasterParseError("Detected fewer than 3 wall segments — image quality may be too low. Try a higher-resolution scan.")``.
- **Test:** ``low_dpi_72.png``.

### Implausible auto-scale
- **Scenario:** Detected scale yields walls outside [2', 80'].
- **Behavior:** Return ``scale_warning``; client retries with ``reference_measurement``.
- **Test:** Custom fixture where detected scale is 10× off.

### Reference measurement override
- **Scenario:** Client supplies ``reference_measurement``.
- **Behavior:** Use it as scale truth; skip auto-detection.
- **Test:** Same fixture as the warning test; pass reference; assert
  walls return with sensible dimensions.

### Very large images
- **Scenario:** >4096 px on longest side.
- **Behavior:** Resize for CV; original image kept for scale calculation.
- **Test:** 8000×6000 fixture (synthesised in test).

### Overlapping YOLO detections
- **Scenario:** Wall box overlaps door/window box.
- **Behavior:** Suppress Hough lines inside the overlap region — wall
  lines terminate at door/window edges.
- **Test:** ``with_doorway.png`` fixture.

## Acceptance Criteria

### AC-1: Raster takeoff produces a valid MaterialTakeoff
- **Given** ``clean_300dpi_scaled.png``
- **When** ``POST /api/takeoff/process/{drawing_id}`` is called
- **Then** response is HTTP 200 with a ``MaterialTakeoff`` containing
  wall count >0, stud quantities >0, plate linear feet >0

### AC-2: Auto-scale detection from a visible scale notation
- **Given** ``clean_300dpi_scaled.png`` (has visible scale)
- **When** the pipeline runs without ``manual_scale`` or ``reference_measurement``
- **Then** the response metadata reflects a detected scale (no
  ``scale_warning``)

### AC-3: Manual scale fallback
- **Given** ``no_scale_annotation.png`` and a ``manual_scale`` parameter
  (e.g., ``"1/4\"=1'-0\""``)
- **When** the pipeline runs
- **Then** the takeoff completes successfully and the metadata records
  the manual scale source

### AC-4: Skew rejection above threshold
- **Given** ``skewed_7deg.png``
- **When** the pipeline runs
- **Then** an error is returned whose message includes the measured
  angle (≈7°)

### AC-5: Skew accepted below threshold
- **Given** ``skewed_3deg.png``
- **When** the pipeline runs
- **Then** the takeoff completes (no skew rejection)

### AC-6: Vector-parity within 10%
- **Given** a floor plan that exists as both a DXF and a scanned PNG
- **When** both are processed
- **Then** raster wall count is within ±10% of vector wall count AND
  raster total linear footage is within ±10% of vector total linear footage

### AC-7: Plausibility-check warning
- **Given** a scan where detected scale produces a wall <2' or >80'
- **When** the pipeline runs
- **Then** the response contains ``scale_warning`` and the takeoff is empty

### AC-8: Reference-measurement override
- **Given** the same scan and ``reference_measurement={wall_index: 0, length_inches: 168}``
- **When** the pipeline runs
- **Then** the takeoff is non-empty and walls fall within plausibility

### AC-9: API routing
- **Given** a drawing with ``file_format`` JPG or PNG
- **When** ``POST /api/takeoff/process/{drawing_id}`` is called
- **Then** the request is routed to ``RasterParser`` (not raised as
  "unsupported format") and returns the standard ``MaterialTakeoff``
  response schema

### AC-10: Sprint 2a regression + new-code coverage
- **Given** the Sprint 3 changes
- **When** ``pytest --cov=app.core.cv --cov=app.core.parsers.raster_parser``
  is run
- **Then** line coverage is ≥80% on the new modules AND all 47 prior
  tests (Sprint 2a + 2c) still pass

## Technical Notes

- **Affected files:**
  - `backend/app/core/parsers/raster_parser.py` (new)
  - `backend/app/core/cv/image_preprocessor.py` (new)
  - `backend/app/core/cv/wall_line_extractor.py` (new)
  - `backend/app/core/cv/scale_detector.py` (new)
  - `backend/app/core/cv/coordinate_converter.py` (new)
  - `backend/app/api/takeoff.py` (drop image rejection, route to RasterParser)
  - `backend/app/schemas/takeoff_request.py` — add optional
    ``manual_scale`` + ``reference_measurement`` fields (or use the existing
    request schema if present)
  - `backend/tests/test_raster_parser.py` (new)
  - `backend/tests/test_image_preprocessor.py` (new)
  - `backend/tests/test_wall_line_extractor.py` (new)
  - `backend/tests/test_scale_detector.py` (new)
  - `backend/tests/fixtures/raster/*.png` (new test fixtures)
- **Out of scope:** Sprint 4 (OCR dimension extraction) is a SEPARATE spec
  at ``llm/features/ocr-dimension-extraction.md``. Sprint 3's ``ScaleDetector``
  may call ``easyocr`` directly within the cascade (lightweight use), but
  the full Sprint 4 OCR pipeline ships separately.
- **Dependencies (runtime):**
  - ``opencv-python`` (already in requirements)
  - ``ultralytics`` (already in requirements; YOLO via model registry)
  - ``easyocr`` (already in requirements)
  - ``google-genai`` (already in requirements; Gemini Vision)
  - Pillow + numpy (already in requirements)
  - No new packages.
- **Dependencies (build/test):** pytest already in requirements after
  Sprint 2b's Gate 1 fix.

## Dependencies

- Sprint 2a VERIFIED (KG-backed lumber dict; calculator unchanged).
- Sprint 2c VERIFIED (health endpoint + smoke test infrastructure;
  used to verify the deployed raster pipeline once live).
- YOLO model registry has an active "floorplan-objects" or equivalent
  Wall-detecting model (already VERIFIED 2026-04-03 in
  ``llm/features/yolo-model-storage.md``).

## Open Questions

- Should Sprint 3 split into 3a (preprocessing + extractor + scale
  detector — pure-CV-no-API) and 3b (RasterParser + API routing +
  end-to-end tests) for cleaner constellize cycles? **Decision:** start
  as one spec; if Phase 4 implementation feels too large, split at that
  point (matches the Sprint 2 → 2a/2b/2c precedent).
- Should we add a ``/api/health/raster`` endpoint that surfaces YOLO model
  status (similar to ``/api/health/kg``)? **Decision:** out of scope here;
  the existing model registry endpoint already covers it. Add to backlog
  if smoke-test feedback shows it's useful.
- Use `cv2.HoughLinesP` vs `LSD` (Line Segment Detector) for wall lines?
  **Decision:** start with `HoughLinesP` (better-known, easier to tune);
  evaluate LSD if accuracy < AC-6 threshold.
- Performance target? **Decision:** <30 s per image on Cloud Run min-tier
  (2 vCPU). Profile during implement; if Cloud Run cold-start + YOLO load
  pushes over, consider a separate worker.
