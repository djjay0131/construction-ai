"""Raster/scanned drawing parser — orchestrates the Sprint 3 CV pipeline.

Same shape as :class:`DXFParser` and :class:`PDFParser`: ``__init__(file_path)``
→ ``load()`` → ``extract_walls(...)``. Result type matches the others
(``list[WallElement]``), so the downstream takeoff API doesn't need a
raster-specific code path beyond the file-format routing.

Collaborators are injectable so tests can swap fakes for everything that
costs real CV / disk I/O.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from app.core.cv.coordinate_converter import CoordinateConverter
from app.core.cv.image_preprocessor import ImagePreprocessor, SkewRejected
from app.core.cv.scale_detector import ScaleDetector, ScaleWarning
from app.core.cv.wall_line_extractor import WallLineExtractor
from app.core.parsers.dxf_parser import WallElement

logger = logging.getLogger(__name__)


class RasterParseError(RuntimeError):
    """Top-level error from the raster pipeline. Message is user-facing."""


def _default_image_loader(path: Path) -> Optional[np.ndarray]:
    """Read an image off disk via cv2.imread. Returns None on failure."""
    return cv2.imread(str(path))


class RasterParser:
    """Orchestrates ImagePreprocessor → WallLineExtractor → ScaleDetector → CoordinateConverter."""

    def __init__(
        self,
        file_path: str | Path,
        preprocessor: Optional[ImagePreprocessor] = None,
        line_extractor: Optional[WallLineExtractor] = None,
        scale_detector: Optional[ScaleDetector] = None,
        image_loader=None,
    ) -> None:
        self.file_path = Path(file_path)
        self.preprocessor = preprocessor or ImagePreprocessor()
        # line_extractor and scale_detector cannot be cheaply defaulted —
        # the extractor needs a YOLO-shaped detector. Callers (the takeoff API)
        # wire the real ones; tests pass fakes.
        self.line_extractor = line_extractor
        self.scale_detector = scale_detector or ScaleDetector()
        self._image_loader = image_loader or _default_image_loader
        self.image: Optional[np.ndarray] = None

    def load(self) -> bool:
        """Read the image from disk. Returns True on success."""
        img = self._image_loader(self.file_path)
        if img is None:
            logger.error("RasterParser.load: cv2.imread returned None for %s", self.file_path)
            return False
        self.image = img
        return True

    def extract_walls(
        self,
        manual_scale: Optional[str] = None,
        reference_measurement: Optional[dict] = None,
    ) -> tuple[list[WallElement], dict]:
        """Run the pipeline. Returns ``(walls, metadata)``.

        ``metadata`` is empty on the happy path; it contains
        ``{"scale_warning": "..."}`` when scale detection fails (the caller
        can then re-invoke with a manual override or reference).

        Raises :class:`RasterParseError` for non-recoverable failures —
        image load failed, image was skewed, or YOLO found no walls.
        """
        if self.image is None and not self.load():
            raise RasterParseError(f"Could not load image {self.file_path}")

        if self.line_extractor is None:
            raise RasterParseError(
                "RasterParser has no line_extractor configured; "
                "the takeoff API wires one with the real YOLO detector."
            )

        try:
            cleaned = self.preprocessor.run(self.image)
        except SkewRejected as exc:
            raise RasterParseError(str(exc)) from exc

        segments_px = self.line_extractor.extract(cleaned)
        if not segments_px:
            raise RasterParseError(
                "No walls detected in image. Try a clearer scan or use the vector pipeline."
            )

        try:
            scale_px_per_in = self.scale_detector.detect(
                cleaned,
                segments_px,
                manual_scale=manual_scale,
                reference=reference_measurement,
            )
        except ScaleWarning as warn:
            return [], {"scale_warning": str(warn)}

        converter = CoordinateConverter(scale_px_per_in)
        walls = converter.to_wall_elements(segments_px)
        return walls, {}
