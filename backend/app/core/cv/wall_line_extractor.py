"""YOLO-constrained Hough wall-line extraction.

Given a preprocessed image and an object detector that returns wall + opening
bounding boxes, extract line segments inside the wall regions while suppressing
lines that pass through openings (doors / windows).

The detector is decoupled via a Protocol so tests can substitute a fake
without importing the real ``DetectionService`` (which pulls in torch +
ultralytics, both heavy and slow to import).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Protocol, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

PixelPoint = Tuple[int, int]
PixelSegment = Tuple[PixelPoint, PixelPoint]
BBox = Tuple[int, int, int, int]  # (x1, y1, x2, y2)


@dataclass(frozen=True)
class Detection:
    """One YOLO detection in image-pixel coordinates."""

    label: str
    bbox: BBox
    confidence: float


class YoloDetector(Protocol):
    """Minimal detector contract — the only thing :class:`WallLineExtractor`
    needs from the model registry side.

    Real implementations: see ``app.core.cv.detection_service``.
    """

    def detect(self, image: np.ndarray) -> list[Detection]: ...  # pragma: no cover


class WallLineExtractor:
    """Extract pixel-space wall line segments from a preprocessed image."""

    OPENING_LABELS = frozenset({"door", "window"})
    WALL_LABEL = "wall"

    def __init__(
        self,
        detector: YoloDetector,
        padding_px: int = 10,
        canny_low: int = 50,
        canny_high: int = 150,
        hough_threshold: int = 50,
        min_line_length: int = 20,
        max_line_gap: int = 10,
    ) -> None:
        if padding_px < 0:
            raise ValueError(f"padding_px must be non-negative; got {padding_px}")
        self.detector = detector
        self.padding_px = padding_px
        self.canny_low = canny_low
        self.canny_high = canny_high
        self.hough_threshold = hough_threshold
        self.min_line_length = min_line_length
        self.max_line_gap = max_line_gap
        # Cache the last extract() detection run so downstream catalog
        # building (Sprint 4d) can reuse them without re-running YOLO.
        self.last_detections: list[Detection] = []

    def extract(self, image: np.ndarray) -> list[PixelSegment]:
        """Return list of ``((x1, y1), (x2, y2))`` segments in image-px coords."""
        if image is None or getattr(image, "size", 0) == 0:
            raise ValueError("extract received empty image")

        detections = self.detector.detect(image)
        self.last_detections = list(detections)
        wall_boxes = [d for d in detections if d.label == self.WALL_LABEL]
        opening_boxes = [d for d in detections if d.label in self.OPENING_LABELS]

        segments: list[PixelSegment] = []
        for wall in wall_boxes:
            segments.extend(self._extract_from_wall(image, wall.bbox, opening_boxes))
        return segments

    def _extract_from_wall(
        self,
        image: np.ndarray,
        wall_bbox: BBox,
        opening_boxes: Iterable[Detection],
    ) -> list[PixelSegment]:
        x1, y1, x2, y2 = self._pad_bbox(wall_bbox, image.shape)
        crop = image[y1:y2, x1:x2]
        if crop.size == 0:
            return []

        gray = (
            cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
        )
        edges = cv2.Canny(gray, self.canny_low, self.canny_high)
        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=self.hough_threshold,
            minLineLength=self.min_line_length,
            maxLineGap=self.max_line_gap,
        )
        if lines is None:
            return []

        out: list[PixelSegment] = []
        for line in lines.reshape(-1, 4):
            x1l, y1l, x2l, y2l = (int(v) for v in line)
            start: PixelPoint = (x1l + x1, y1l + y1)
            end: PixelPoint = (x2l + x1, y2l + y1)
            mid = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
            if any(self._point_in_box(mid, ob.bbox) for ob in opening_boxes):
                continue
            out.append((start, end))
        return out

    def _pad_bbox(
        self, bbox: BBox, image_shape: tuple[int, ...]
    ) -> BBox:
        """Inflate ``bbox`` by ``self.padding_px`` on each side, clipped to image bounds."""
        h, w = image_shape[:2]
        x1, y1, x2, y2 = bbox
        return (
            max(0, x1 - self.padding_px),
            max(0, y1 - self.padding_px),
            min(w, x2 + self.padding_px),
            min(h, y2 + self.padding_px),
        )

    @staticmethod
    def _point_in_box(point: tuple[float, float], bbox: BBox) -> bool:
        px, py = point
        x1, y1, x2, y2 = bbox
        return x1 <= px <= x2 and y1 <= py <= y2
