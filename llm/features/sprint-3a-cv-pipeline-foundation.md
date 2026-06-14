# Sprint 3a: CV Pipeline Foundation (Preprocessor + Converter)

**Status:** VERIFIED
**Date:** 2026-06-14
**Implemented:** 2026-06-14
**Verified:** 2026-06-14
**Author:** Jason Cusati (with AI assistance)
**Sprint:** 3a of 2 (Sprint 3 — Raster/Scanned Drawing Support)
**Supersedes:** the "Pure-CV" slice of
`llm/features/sprint-3-raster-scanned-drawing-support.md` (SPECIFIED 2026-06-10).
3b will ship the remaining modules (`WallLineExtractor`, `ScaleDetector`,
`RasterParser`, API routing, e2e tests).

## Problem

Sprint 3 (full) requires 5 new modules + API integration + 6 image
fixtures (~800 LOC code + ~580 LOC tests). To match the Sprint 2 →
2a/2b/2c cadence and keep each constellize cycle verifiable in isolation,
3a ships the two cleanest-contract components — the ones that operate on
plain numpy arrays and need no YOLO model, no Gemini, no real image
fixtures.

## Goals

- `ImagePreprocessor` rejects images skewed > 5° via a clear, actionable
  exception that names the measured angle.
- `ImagePreprocessor` enhances accepted images (CLAHE contrast + Gaussian
  denoise) and returns the result for downstream consumption.
- `CoordinateConverter` translates per-segment pixel coordinates into the
  application's `WallElement[]` schema using a known pixels-per-inch scale.
- Both modules are testable against synthetic numpy arrays — no real
  scanned plans needed in 3a; that's 3b's scope.
- ≥80% line coverage on the new modules.
- Zero regression in the 47 Sprint 2 tests.

## Non-Goals

- **YOLO object detection** — 3b.
- **Hough wall-line extraction** — 3b.
- **Scale detection cascade (Gemini / OCR / manual)** — 3b.
- **RasterParser orchestration** — 3b.
- **API routing in `app/api/takeoff.py`** — 3b.
- **Real image fixtures (clean_300dpi, skewed_Ndeg, etc.)** — 3b.
- **End-to-end takeoff parity with the vector pipeline** — 3b.

## Design Approach

### `ImagePreprocessor` (`backend/app/core/cv/image_preprocessor.py`)

A simple class with two public methods + one exception.

```python
class SkewRejected(RuntimeError):
    """Raised when measured skew exceeds the threshold (default 5°).
    Message always includes the measured angle so the user can see how
    far off the input was.
    """

class ImagePreprocessor:
    def __init__(self, skew_threshold_deg: float = 5.0): ...

    def detect_skew(self, image: np.ndarray) -> float:
        """Return the dominant edge-orientation deviation from horizontal
        in degrees, signed. Uses cv2.HoughLines on a Canny edge map and
        takes the median of detected line angles modulo 90°."""

    def run(self, image: np.ndarray) -> np.ndarray:
        """Full preprocessing pipeline: detect skew → reject if over
        threshold → CLAHE enhance → Gaussian denoise → return."""
```

Skew-detection algorithm (deterministic, testable):

1. Convert to grayscale if needed.
2. Canny edge map (low_threshold=50, high_threshold=150).
3. `cv2.HoughLines(edges, 1, π/180, threshold=100)` → list of (ρ, θ).
4. For each θ in [0, π), compute the deviation from the nearest axis (0
   or π/2). Take the median deviation. That's the skew angle in radians;
   convert to degrees.

Enhancement steps (in `run`):

1. Convert to grayscale.
2. CLAHE with `clipLimit=2.0, tileGridSize=(8, 8)`.
3. Gaussian blur with `ksize=(3, 3), sigmaX=0` (light denoise — too
   aggressive and we lose wall edges).

### `CoordinateConverter` (`backend/app/core/cv/coordinate_converter.py`)

Pure-math helper. No image input.

```python
class CoordinateConverter:
    def __init__(self, scale_px_per_in: float): ...

    def to_wall_elements(
        self,
        segments_px: list[tuple[tuple[float, float], tuple[float, float]]],
    ) -> list[WallElement]:
        """Convert pixel-coordinate line segments to WallElement[].

        Each segment is (start_pt, end_pt) in pixel coordinates. The
        converter divides by scale_px_per_in to get inches, then constructs
        a WallElement using the existing WallElement(start_point, end_point,
        thickness, layer) signature from dxf_parser.WallElement.
        """
```

Reuses the existing `WallElement` class from `app.core.parsers.dxf_parser`
unchanged — that's the whole point of the parser-interface contract.

Default thickness: 4 inches (interior 2×4 wall), default layer:
`"raster"`. Both overridable via kwargs.

### Module structure

Both modules live in `backend/app/core/cv/` next to the existing
`detection_service.py` / `floor_plan_service.py`. Both have module-level
docstrings; the package `__init__.py` doesn't re-export them (consumers
import from the specific submodule).

## Sample Implementation

```python
# === backend/app/core/cv/image_preprocessor.py ===
from __future__ import annotations

import logging
import numpy as np
import cv2

logger = logging.getLogger(__name__)


class SkewRejected(RuntimeError):
    """Raised when input image skew exceeds the threshold."""


class ImagePreprocessor:
    """Preprocess raster/scanned drawings: reject skewed; enhance the rest."""

    def __init__(self, skew_threshold_deg: float = 5.0) -> None:
        if skew_threshold_deg <= 0:
            raise ValueError(f"skew_threshold_deg must be positive; got {skew_threshold_deg}")
        self.skew_threshold_deg = skew_threshold_deg

    def detect_skew(self, image: np.ndarray) -> float:
        """Return the dominant skew angle in degrees (signed)."""
        if image is None or image.size == 0:
            raise ValueError("detect_skew received empty image")

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        edges = cv2.Canny(gray, 50, 150)
        lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=100)

        if lines is None or len(lines) == 0:
            return 0.0

        angles_deg = []
        for rho_theta in lines:
            theta = rho_theta[0][1]
            # Deviation from nearest axis (0 or π/2), mapped to (-45, 45] degrees
            dev_rad = ((theta + np.pi / 4) % (np.pi / 2)) - np.pi / 4
            angles_deg.append(np.degrees(dev_rad))

        return float(np.median(angles_deg))

    def run(self, image: np.ndarray) -> np.ndarray:
        """Full preprocessing: reject if skewed, otherwise enhance + return."""
        skew = self.detect_skew(image)
        if abs(skew) > self.skew_threshold_deg:
            raise SkewRejected(
                f"Drawing appears skewed by {skew:.1f} degrees "
                f"(threshold {self.skew_threshold_deg:.1f}). "
                "Please provide a properly scanned image."
            )

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        denoised = cv2.GaussianBlur(enhanced, (3, 3), 0)
        return denoised


# === backend/app/core/cv/coordinate_converter.py ===
from __future__ import annotations

import logging
from typing import Iterable, Tuple

from app.core.parsers.dxf_parser import WallElement

logger = logging.getLogger(__name__)

PixelSegment = Tuple[Tuple[float, float], Tuple[float, float]]


class CoordinateConverter:
    """Translate pixel-space line segments into the project's WallElement[] shape."""

    def __init__(
        self,
        scale_px_per_in: float,
        default_thickness_in: float = 4.0,
        default_layer: str = "raster",
    ) -> None:
        if scale_px_per_in <= 0:
            raise ValueError(f"scale_px_per_in must be positive; got {scale_px_per_in}")
        self.scale_px_per_in = scale_px_per_in
        self.default_thickness_in = default_thickness_in
        self.default_layer = default_layer

    def to_wall_elements(self, segments_px: Iterable[PixelSegment]) -> list[WallElement]:
        return [self._make_wall(start_px, end_px) for start_px, end_px in segments_px]

    def _make_wall(
        self, start_px: Tuple[float, float], end_px: Tuple[float, float]
    ) -> WallElement:
        start_in = (start_px[0] / self.scale_px_per_in, start_px[1] / self.scale_px_per_in)
        end_in   = (end_px[0]   / self.scale_px_per_in, end_px[1]   / self.scale_px_per_in)
        return WallElement(
            start_point=start_in,
            end_point=end_in,
            thickness=self.default_thickness_in,
            layer=self.default_layer,
        )
```

## Edge Cases & Error Handling

### Empty image / None
- **Scenario:** `detect_skew(None)` or zero-size array.
- **Behavior:** Raise `ValueError("detect_skew received empty image")`.
- **Test:** Pass `None` and zero-size array; expect `ValueError`.

### No edges found by Canny
- **Scenario:** Blank or near-blank image — Hough returns no lines.
- **Behavior:** Skew defaults to 0° (no deviation detectable); `run` enhances and returns. Downstream wall extraction will likely fail later, but preprocessor doesn't know that.
- **Test:** Pass a uniform-gray array; expect skew == 0.0 and `run` to return.

### Skew exactly at threshold
- **Scenario:** `abs(skew) == skew_threshold_deg`.
- **Behavior:** **Accept** (strict `>` comparison). At threshold = pass.
- **Test:** Mock `detect_skew` to return exactly 5.0; expect `run` to succeed.

### Color image vs grayscale input
- **Scenario:** Image arrives as either 3-channel BGR or single-channel.
- **Behavior:** Both supported via `ndim` check.
- **Test:** Both shapes.

### Non-positive thresholds at construction
- **Scenario:** Caller passes negative or zero `skew_threshold_deg`.
- **Behavior:** Raise `ValueError` at `__init__`.
- **Test:** Both -1 and 0.

### Empty segment list
- **Scenario:** `to_wall_elements([])`.
- **Behavior:** Return `[]`.
- **Test:** Pass empty input.

### Non-positive scale
- **Scenario:** `CoordinateConverter(scale_px_per_in=0)` or negative.
- **Behavior:** Raise `ValueError` at `__init__`.
- **Test:** 0 and -1.

## Acceptance Criteria

### AC-1: Skew rejection above threshold
- **Given** an image whose detected skew angle exceeds 5°
- **When** `ImagePreprocessor().run(image)` is called
- **Then** `SkewRejected` is raised
- **And** the error message includes the measured angle

### AC-2: Skew accepted at or below threshold
- **Given** an image whose detected skew is at or below 5°
- **When** `ImagePreprocessor().run(image)` is called
- **Then** a numpy array of the same shape (single channel) is returned
- **And** no exception is raised

### AC-3: Custom threshold respected
- **Given** `ImagePreprocessor(skew_threshold_deg=2.0)` and an image with 3° skew
- **When** `run` is called
- **Then** `SkewRejected` is raised

### AC-4: Construction validation
- **Given** `ImagePreprocessor(skew_threshold_deg=0)` or negative
- **When** the constructor runs
- **Then** `ValueError` is raised at construction time

### AC-5: detect_skew handles both color and grayscale input
- **Given** an image with `ndim == 2` and one with `ndim == 3`
- **When** `detect_skew(image)` is called on each
- **Then** both return a float (no shape error)

### AC-6: CoordinateConverter happy path
- **Given** a CoordinateConverter with `scale_px_per_in=10.0`
- **When** `to_wall_elements([((0, 0), (100, 0))])` is called
- **Then** the result is a single `WallElement` whose endpoints are
  `(0.0, 0.0)` and `(10.0, 0.0)` in inches (10.0-inch wall)

### AC-7: CoordinateConverter empty input
- **Given** any valid converter
- **When** `to_wall_elements([])` is called
- **Then** `[]` is returned (no exception)

### AC-8: CoordinateConverter rejects non-positive scale
- **Given** `CoordinateConverter(scale_px_per_in=0)` or negative
- **When** the constructor runs
- **Then** `ValueError` is raised

### AC-9: CoordinateConverter preserves WallElement shape
- **Given** any valid conversion
- **When** the result is inspected
- **Then** each item is a `WallElement` (the existing class from
  `app.core.parsers.dxf_parser`) with `length_inches > 0`

### AC-10: ≥80% line coverage + Sprint 2 regression
- **Given** the implementation is complete
- **When** `pytest tests/test_image_preprocessor.py tests/test_coordinate_converter.py --cov=app.core.cv.image_preprocessor --cov=app.core.cv.coordinate_converter`
- **Then** line coverage is ≥80% on each module
- **And** the 47 Sprint 2 tests (kg + lumber refactor + health endpoint +
  smoke test) still pass

## Technical Notes

- **Affected files:**
  - `backend/app/core/cv/image_preprocessor.py` (new)
  - `backend/app/core/cv/coordinate_converter.py` (new)
  - `backend/tests/test_image_preprocessor.py` (new)
  - `backend/tests/test_coordinate_converter.py` (new)
- **No new runtime dependencies** — `cv2`, `numpy`, and `WallElement`
  are all already in the project.
- **No fixtures needed.** All test inputs are synthetic numpy arrays
  constructed in-test.
- **Not added to CI workflow yet.** CI explicit test list adds these in
  Sprint 3b along with the wall-extractor/scale-detector tests.

## Dependencies

- Sprint 2a VERIFIED (KG-backed `LumberCalculator` consumes `WallElement[]`
  unchanged).
- `WallElement` defined at `backend/app/core/parsers/dxf_parser.py` line 37.

## Open Questions

- Should `ImagePreprocessor.run` also deskew slightly-tilted images
  (e.g., 1–2°) before enhancement? **Decision:** no — standing project
  policy from earlier specs says skewed drawings are rejected, not
  corrected. Even small skews get rejected if over threshold.
- Should `CoordinateConverter` accept variable per-wall thickness?
  **Decision:** not in 3a — Sprint 3b's `WallLineExtractor` will pair
  parallel lines and report measured thicknesses; converter will accept
  that as a kwarg then.

## Implementation Log (2026-06-14)

**Files created:**
- `backend/app/core/cv/image_preprocessor.py` (34 stmts).
- `backend/app/core/cv/coordinate_converter.py` (19 stmts).
- `backend/tests/test_image_preprocessor.py` (16 tests).
- `backend/tests/test_coordinate_converter.py` (11 tests).

**Tests: 27/27 pass, 100% line coverage** on both new modules.

**AC mapping:**
| AC | Covered by |
|---|---|
| AC-1: skew >5° rejected | `test_run_rejects_when_skew_over_threshold`, `test_run_rejects_negative_skew_over_threshold`, `test_run_rejects_just_over_threshold` |
| AC-2: skew ≤5° accepted | `test_run_accepts_clean_image`, `test_run_accepts_exactly_at_threshold`, `test_run_accepts_just_under_threshold` |
| AC-3: custom threshold | `test_custom_threshold_respected` |
| AC-4: ctor validation | `TestConstructorValidation` (both modules) |
| AC-5: color vs grayscale | `test_three_channel_image_handled`, `test_color_input_returns_single_channel` |
| AC-6: happy path | `test_single_horizontal_segment_produces_correct_wall` |
| AC-7: empty input | `test_empty_input_returns_empty_list` |
| AC-8: non-positive scale | `TestConstructorValidation` (converter) |
| AC-9: WallElement preservation | `TestPreservesWallElementShape` |
| AC-10: ≥80% coverage + Sprint 2 regression | **100%** coverage; Sprint 2 tests still pass (66/66 non-integration; 8 testcontainer-gated tests pass when Docker is up) |

**Coverage pragmas:** none.

**Deviations from spec:** none.

**Dependencies installed during implementation:** `opencv-python` into the
local venv (was missing — wasn't a runtime issue since Cloud Run uses the
full requirements.txt, but local pytest couldn't import cv2 until install).
