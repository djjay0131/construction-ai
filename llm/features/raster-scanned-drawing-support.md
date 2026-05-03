# Feature: Raster/Scanned Drawing Support

**Status:** SPECIFIED (reviewed)
**Date:** 2026-04-01
**Author:** Feature Architect (AI-assisted)

## Problem

Users with scanned or photographed construction drawings (JPG, PNG) cannot run material takeoffs because the takeoff pipeline only handles vector formats (DXF/DWG/PDF). The upload API already accepts image files and the CV infrastructure (YOLOv8, EasyOCR, Gemini Vision) exists, but there is no conversion path from pixel data to the `WallElement[]` geometry that `LumberCalculator` requires. This blocks a significant class of users — anyone working from paper plans, old archives, or on-site phone photos.

## Goals

- Full material takeoff parity with vector pipeline: raster input produces identical `MaterialTakeoff` output (studs, plates, lumber list)
- Automatic scale detection from title blocks, scale bars, or dimension annotations
- Handle variable image quality: contrast enhancement, noise reduction
- Reject skewed drawings (>5 degrees) with clear error message — drawings must be properly scanned
- Accuracy target: within 10% of vector pipeline takeoff on the same drawing

## Non-Goals

- Multi-page raster support (single image per upload for now; multi-page is backlog item 1.6)
- Training a custom YOLO model (depends on backlog item 2.1; use existing `best.pt` or pre-trained weights)
- Robustness to heavily degraded scans (severe shadows, creases, low contrast, compression artifacts). Initial implementation targets clean-to-moderate quality scans (300+ DPI, minimal noise). Degraded image handling is a follow-up after the core pipeline is validated.
- 3D or isometric drawing interpretation
- Handwritten sketch interpretation
- Automated floor plan generation from photos of built structures

## User Stories

- As a contractor, I want to upload a scanned floor plan image and get a full material takeoff, so that I can generate lumber lists from old paper drawings.
- As a project manager, I want the system to automatically detect the drawing scale from a scanned plan, so that I don't have to manually calculate pixel-to-inch ratios.
- As a field worker, I want to photograph a drawing on-site and get a material estimate, so that I can quickly verify quantities without returning to the office.

## Design Approach

### Architecture

The raster pipeline adds a new parser (`RasterParser`) that slots into the existing takeoff flow alongside `PDFParser` and `DXFParser`. It produces the same `WallElement[]` output, so downstream code (`LumberCalculator`, takeoff API) requires no changes.

```
Image Upload → RasterParser
                 ├── Preprocessing (skew detection + reject, enhance, denoise)
                 ├── YOLO Object Detection (walls, doors, windows, columns)
                 ├── Wall Line Extraction (Hough lines WITHIN YOLO wall regions only)
                 │     └── For each YOLO "Wall" bbox:
                 │           ├── Crop region + padding
                 │           ├── Canny edge detection
                 │           ├── Morphological closing
                 │           ├── Probabilistic Hough line transform
                 │           └── Map line coords back to full image
                 ├── Parallel Line Pairing (detect wall thickness from paired lines)
                 ├── Segment Merging (join collinear fragments across regions)
                 ├── Scale Detection (Gemini → OCR → manual fallback)
                 └── Coordinate Conversion (pixels → inches → WallElement[])
                          │
                          ▼
               LumberCalculator (unchanged)
                          │
                          ▼
                  MaterialTakeoff output
```

### Key Components

1. **`RasterParser`** (`backend/app/core/parsers/raster_parser.py`) — Main parser class, mirrors `PDFParser`/`DXFParser` interface.

2. **`ImagePreprocessor`** (`backend/app/core/cv/image_preprocessor.py`) — Skew detection via Hough transform dominant angle analysis (reject if >5 degrees), CLAHE contrast enhancement, Gaussian denoising, adaptive thresholding.

3. **`WallLineExtractor`** (`backend/app/core/cv/wall_line_extractor.py`) — Uses YOLO "Wall" bounding boxes as regions of interest. For each wall region: crop with padding → Canny edge detection → morphological closing → probabilistic Hough line transform → map coordinates back to full image. Then: parallel line pairing to detect wall thickness → centerline extraction → collinear segment merging across regions. This eliminates noise from dimension lines, furniture, grid lines, and text that would pollute a full-image Hough approach.

4. **`ScaleDetector`** (`backend/app/core/cv/scale_detector.py`) — Cascade: Gemini Vision title block analysis → EasyOCR dimension annotation matching → user-provided manual scale. After auto-detection, runs a **plausibility check**: applies detected scale to all wall segments and verifies results fall within residential bounds (no wall <2' or >80', total footprint <20,000 sqft). If plausibility fails, returns a `scale_warning` flag prompting the user to provide a known reference measurement for validation. User-provided reference measurement is optional but used as ground truth when provided.

5. **Takeoff API update** — Remove the image format rejection in `takeoff.py:215-219`, add raster format routing.

### Data Flow

1. User uploads JPG/PNG via existing upload endpoint
2. Takeoff API routes to `RasterParser` based on `DrawingFormat`
3. `RasterParser` preprocesses image, runs YOLO detection, extracts wall lines
4. Wall pixel coordinates converted to real-world inches using detected scale
5. `WallElement[]` passed to `LumberCalculator` — identical path as DXF/PDF

## Sample Implementation

```python
# raster_parser.py — Core logic (simplified)

class RasterParser:
    """Parser for raster/scanned architectural drawings (JPG, PNG)."""

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.image: Optional[np.ndarray] = None
        self.walls: list[WallElement] = []
        self.preprocessor = ImagePreprocessor()
        self.line_extractor = WallLineExtractor()
        self.scale_detector = ScaleDetector()

    def load(self) -> bool:
        self.image = cv2.imread(str(self.file_path))
        return self.image is not None

    def extract_walls(self, manual_scale: str = None) -> list[WallElement]:
        # 1. Preprocess: detect skew (reject if >5 degrees) + enhance
        skew_angle = self.preprocessor.detect_skew(self.image)
        if abs(skew_angle) > 5.0:
            raise ValueError(
                f"Drawing appears skewed by {skew_angle:.1f} degrees. "
                "Please provide a properly scanned, non-skewed image."
            )
        enhanced = self.preprocessor.enhance(self.image)

        # 2. Detect all objects (walls, doors, windows) via YOLO
        detection_service = get_detection_service()
        detections, _ = detection_service.detect_objects(
            str(self.file_path), confidence=0.25
        )

        # 3. Separate wall regions from door/window detections
        wall_boxes = [
            obj.bbox for obj in detections.detected_objects
            if obj.class_name == "Wall"
        ]
        opening_boxes = [
            obj.bbox for obj in detections.detected_objects
            if obj.class_name in ("Door", "Window", "Sliding Door")
        ]

        if not wall_boxes:
            raise ValueError(
                "No wall regions detected in image. "
                "Ensure the image is a clear floor plan drawing."
            )

        # 4. Extract wall lines via Hough — ONLY within YOLO wall regions
        #    This eliminates noise from dimension lines, furniture, text, etc.
        raw_lines = self.line_extractor.extract_within_regions(
            enhanced, wall_boxes, padding=20
        )

        # 5. Pair parallel lines to find wall centerlines + thickness
        #    Falls back to treating unpaired strong lines as centerlines
        centerlines, unpaired = self.line_extractor.pair_parallel_lines(
            raw_lines, min_gap=3, max_gap=30  # pixels
        )
        centerlines.extend(unpaired)  # single thick lines treated as walls too

        # 6. Merge collinear segments across regions
        merged = self.line_extractor.merge_collinear(centerlines)

        # 6. Determine scale (pixels per inch)
        px_per_inch = self.scale_detector.detect(
            self.image, manual_scale=manual_scale
        )
        if not px_per_inch:
            raise ValueError(
                "Could not determine drawing scale. "
                "Please provide scale manually."
            )

        # 7. Convert to WallElement with real-world coordinates
        self.walls = []
        for (x1, y1, x2, y2) in merged:
            start = (x1 / px_per_inch, y1 / px_per_inch)
            end = (x2 / px_per_inch, y2 / px_per_inch)
            self.walls.append(WallElement(
                start_point=start, end_point=end,
                layer="raster_detected",
                metadata={
                    "source": "raster",
                    "confidence": yolo_conf * hough_strength,  # composite score
                    "yolo_confidence": yolo_conf,       # from YOLO wall region
                    "hough_strength": hough_strength,   # from Hough line votes
                    "extraction_method": "yolo_hough",
                }
            ))

        return self.walls

    def get_drawing_info(self) -> dict:
        h, w = self.image.shape[:2]
        return {
            "filename": self.file_path.name,
            "format": "raster",
            "width_px": w,
            "height_px": h,
            "units": "pixels (scale-dependent)",
        }
```

## Edge Cases & Error Handling

### No Scale Detected
- **Scenario**: Gemini Vision and OCR both fail to find scale notation
- **Behavior**: Raise `ValueError` with message prompting user to provide manual scale. API returns 422 with instructions.
- **Test**: Upload image with no title block or scale notation, verify error message and manual scale parameter works.

### Implausible Scale Detected
- **Scenario**: Auto-detected scale produces wall lengths outside residential bounds (e.g., walls >80' or <2', footprint >20,000 sqft)
- **Behavior**: Return takeoff result with a `scale_warning` flag and message asking user to provide a known reference measurement (e.g., "the master bedroom wall is 14 feet"). If user provides a reference, recalculate scale from that measurement and re-run. Do not silently proceed with implausible dimensions.
- **Test**: Feed an image with an intentionally wrong scale annotation. Verify the plausibility check catches it and the warning is returned.

### Skewed Image
- **Scenario**: Image scanned or photographed at an angle (>5 degrees of skew)
- **Behavior**: Reject with clear error message stating the detected skew angle and requesting a properly scanned image. Drawing is assumed to-scale, so skewed inputs would produce inaccurate geometric measurements.
- **Test**: Rotate a known test image by 3, 5, and 10 degrees. Verify 3 degrees passes, 5+ degrees is rejected with the correct angle in the error message.

### Low Resolution / Blurry Image
- **Scenario**: Image below 150 DPI or significant blur
- **Behavior**: Preprocessing enhances contrast and sharpens, but if Hough line detection finds <3 wall segments, return error suggesting higher quality scan.
- **Test**: Downsample a test image to 72 DPI and 150 DPI. Verify graceful failure at 72 DPI and successful extraction at 150 DPI.

### Overlapping YOLO Detections
- **Scenario**: YOLO wall bounding box overlaps with a door/window bounding box, or two wall regions overlap
- **Behavior**: When a wall region overlaps with a door/window region, Hough lines within the overlap are suppressed — wall lines terminate at opening edges. Overlapping wall regions are unioned before Hough extraction to avoid duplicate lines.
- **Test**: Use image with a doorway in a wall. Verify wall lines extend to door edges but don't cross through.

### No Wall Regions Detected by YOLO
- **Scenario**: YOLO model fails to detect any "Wall" class objects (poor model, unusual drawing style)
- **Behavior**: Raise `ValueError` with message explaining no walls were detected. Suggest uploading a clearer image or using the vector pipeline.
- **Test**: Upload a photograph (not a floor plan). Verify clear error message, no crash.

### Very Large Images
- **Scenario**: High-resolution scan (>10000px, >50MB)
- **Behavior**: Resize to max 4096px on longest side for CV processing, maintain original for scale calculation.
- **Test**: Upload 8000x6000px image. Verify processing completes without OOM and dimensions are accurate.

### Curved or Diagonal Walls
- **Scenario**: Floor plan contains non-orthogonal walls
- **Behavior**: Hough line detection captures diagonal lines. Curved walls approximated as chord segments. Metadata flags non-orthogonal walls with a warning.
- **Test**: Use test image with 45-degree and curved walls. Verify diagonal walls are captured and curves produce a warning.

## Acceptance Criteria

### AC-1: Basic Raster Takeoff
- **Given** a high-quality scanned floor plan image (300 DPI, no skew, visible scale)
- **When** the user uploads it and triggers a takeoff
- **Then** the system produces a `MaterialTakeoff` with wall count, stud quantities, and plate lengths

### AC-2: Scale Detection
- **Given** a scanned floor plan with a visible scale notation in the title block
- **When** the system processes the image
- **Then** the scale is automatically detected and applied to convert pixel measurements to real-world dimensions

### AC-3: Manual Scale Fallback
- **Given** a scanned floor plan with no detectable scale
- **When** the user provides a manual scale parameter (e.g., `1/4"=1'-0"`)
- **Then** the manual scale is used and the takeoff completes successfully

### AC-4: Skew Rejection
- **Given** a scanned floor plan image with >5 degrees of rotation
- **When** the system preprocesses the image
- **Then** the image is rejected with a clear error message stating the detected skew angle

### AC-5: Parity with Vector Pipeline
- **Given** a floor plan that exists in both DXF and scanned image form
- **When** both are processed through their respective pipelines
- **Then** the raster takeoff wall count is within 10% of the vector takeoff wall count AND total linear footage is within 10% of the vector takeoff linear footage

### AC-6: Graceful Failure
- **Given** an image that is too low quality for reliable extraction (e.g., <100 DPI, severe blur)
- **When** processing is attempted
- **Then** the system returns a clear error message explaining the issue, not a crash or empty result

### AC-7: Scale Plausibility Check
- **Given** a scanned floor plan where auto-detected scale produces walls outside residential bounds (any wall <2' or >80')
- **When** the system processes the image
- **Then** the response includes a `scale_warning` flag and message prompting the user to provide a known reference measurement

### AC-8: Reference Measurement Override
- **Given** a scale warning has been returned
- **When** the user provides a reference measurement (e.g., wall index + known length)
- **Then** the system recalculates scale from that reference and produces a corrected takeoff

### AC-9: API Integration
- **Given** an uploaded JPG/PNG drawing
- **When** the user calls `POST /api/takeoff/process/{drawing_id}`
- **Then** the takeoff pipeline routes to `RasterParser` and returns the same response schema as DXF/PDF takeoffs

## Technical Notes

- **Affected components:**
  - `backend/app/api/takeoff.py` — add raster format routing (remove lines 215-219 rejection)
  - `backend/app/core/parsers/` — new `raster_parser.py`
  - `backend/app/core/cv/` — new `image_preprocessor.py`, `wall_line_extractor.py`, `scale_detector.py`
  - `backend/app/core/cv/detection_service.py` — reused as-is
  - `backend/app/core/cv/floor_plan_service.py` — reuse `analyze_with_gemini()` and `extract_scale_info()` methods

- **Patterns to follow:**
  - Parser interface: `load() → bool`, `extract_walls() → list[WallElement]`, `get_drawing_info() → dict` (matches `PDFParser`, `DXFParser`)
  - Singleton service pattern (matches `get_detection_service()`, `get_floor_plan_service()`)
  - Pydantic schemas for API responses (matches existing `MaterialTakeoff` schema)

- **Data model changes:** `DrawingFormat` enum already includes PNG/JPG/JPEG. `WallElement` reused as-is. The `MaterialTakeoff.notes` list should include an `extraction_source: raster` indicator and an average wall confidence score so the user knows this takeoff came from CV extraction and may warrant visual verification. The `processing_metadata` on `MaterialTakeoffRecord` should store per-wall confidence scores for auditability.

- **Dependencies (already installed):**
  - `opencv-python` (cv2) — image processing, Hough transform
  - `ultralytics` (YOLO) — object detection
  - `easyocr` — OCR for dimension extraction
  - `google-genai` — Gemini Vision for scale detection
  - `numpy`, `Pillow` — image manipulation

## Dependencies

- **Backlog 2.1 (YOLOv8 Training)** — Soft dependency. Raster pipeline can work with the existing `best.pt` model for door/window detection, but accuracy improves significantly with a model trained on construction floor plan drawings. The wall extraction itself uses Hough lines, not YOLO.
- **Existing `DetectionService`** — Reused for object detection. Must have a loaded YOLO model (`best.pt`).
- **Existing `FloorPlanAnalysisService`** — Gemini Vision and scale parsing logic reused or refactored into `ScaleDetector`.

## Open Questions

- **YOLO model availability:** Does a suitable `best.pt` exist for floor plan objects, or will we need to train one first (backlog 2.1)? The wall extraction pipeline (Hough lines) is independent of YOLO, but door/window filtering accuracy depends on it.
- **Scale detection reliability:** How often will Gemini Vision successfully extract scale from scanned drawings? May need to track success rate and tune prompts.
- **Integration with `FloorPlanAnalysisService`:** Should `RasterParser` reuse the existing service's methods directly, or should shared logic (scale detection, Gemini calls) be refactored into standalone utilities?
- **Plausibility bounds tuning:** The residential bounds (wall <2' or >80', footprint <20,000 sqft) are reasonable defaults but may need adjustment for commercial or multi-family projects if scope expands.
- **Single-line vs double-line wall detection:** The fallback from parallel-pair to single-line works, but the two modes may produce different wall thickness assumptions. Should the lumber calculator account for detected wall thickness, or always assume standard 2x4/2x6?
