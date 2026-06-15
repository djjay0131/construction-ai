"""Unit tests for ``app.core.cv.wall_line_extractor``.

Uses a fake ``YoloDetector`` instead of real YOLO so the test suite
doesn't load torch / ultralytics.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.core.cv.wall_line_extractor import (
    Detection,
    WallLineExtractor,
    YoloDetector,
)


class FakeDetector:
    """Test-only detector. Returns whatever it was constructed with."""

    def __init__(self, detections: list[Detection]) -> None:
        self._detections = list(detections)

    def detect(self, image: np.ndarray) -> list[Detection]:
        return self._detections


def _grid_image(size: int = 400) -> np.ndarray:
    """White image with a black-line grid — generates plenty of edges."""
    img = np.full((size, size), 255, dtype=np.uint8)
    for y in range(50, size, 50):
        cv2.line(img, (0, y), (size, y), 0, thickness=2)
    for x in range(50, size, 50):
        cv2.line(img, (x, 0), (x, size), 0, thickness=2)
    return img


def _det(label: str, bbox, confidence: float = 0.9) -> Detection:
    return Detection(label=label, bbox=tuple(bbox), confidence=confidence)


class TestConstructorValidation:
    def test_negative_padding_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            WallLineExtractor(detector=FakeDetector([]), padding_px=-1)


class TestExtractInputValidation:
    def test_none_image_raises(self):
        with pytest.raises(ValueError, match="empty image"):
            WallLineExtractor(detector=FakeDetector([])).extract(None)

    def test_zero_size_image_raises(self):
        with pytest.raises(ValueError, match="empty image"):
            WallLineExtractor(detector=FakeDetector([])).extract(np.zeros((0, 0), dtype=np.uint8))


class TestNoDetections:
    def test_no_wall_boxes_returns_empty(self):
        ext = WallLineExtractor(detector=FakeDetector([]))
        assert ext.extract(_grid_image()) == []

    def test_only_opening_boxes_returns_empty(self):
        ext = WallLineExtractor(
            detector=FakeDetector([_det("door", (10, 10, 50, 50))])
        )
        assert ext.extract(_grid_image()) == []


class TestExtractFromWall:
    def test_wall_region_with_grid_finds_lines(self):
        # One wall bbox covering the whole grid — Hough should find plenty.
        ext = WallLineExtractor(
            detector=FakeDetector([_det("wall", (0, 0, 400, 400))])
        )
        segments = ext.extract(_grid_image())
        assert len(segments) > 0
        # Every segment is a valid pair of points
        for start, end in segments:
            assert len(start) == 2 and len(end) == 2

    def test_blank_wall_region_returns_nothing(self):
        # Wall bbox covering a uniform-white image — no edges, no lines.
        blank = np.full((400, 400), 255, dtype=np.uint8)
        ext = WallLineExtractor(
            detector=FakeDetector([_det("wall", (0, 0, 400, 400))])
        )
        assert ext.extract(blank) == []


class TestOpeningSuppression:
    def test_lines_inside_door_bbox_are_dropped(self):
        # Wall covers whole image; door covers the center 100×100 square.
        ext = WallLineExtractor(
            detector=FakeDetector(
                [
                    _det("wall", (0, 0, 400, 400)),
                    _det("door", (150, 150, 250, 250)),
                ]
            )
        )
        segments = ext.extract(_grid_image())
        for start, end in segments:
            mid_x = (start[0] + end[0]) / 2
            mid_y = (start[1] + end[1]) / 2
            inside = 150 <= mid_x <= 250 and 150 <= mid_y <= 250
            assert not inside, "no segment midpoint should fall inside the door bbox"

    def test_window_label_also_suppresses(self):
        # Window class should be treated the same as door for suppression.
        ext = WallLineExtractor(
            detector=FakeDetector(
                [
                    _det("wall", (0, 0, 400, 400)),
                    _det("window", (150, 150, 250, 250)),
                ]
            )
        )
        segments = ext.extract(_grid_image())
        for start, end in segments:
            mid_x = (start[0] + end[0]) / 2
            mid_y = (start[1] + end[1]) / 2
            inside = 150 <= mid_x <= 250 and 150 <= mid_y <= 250
            assert not inside


class TestBboxPadding:
    def test_pad_bbox_clips_to_image_bounds(self):
        ext = WallLineExtractor(detector=FakeDetector([]), padding_px=100)
        # Wall bbox at top-left corner; padding would push beyond (0,0).
        padded = ext._pad_bbox((0, 0, 50, 50), (200, 200))
        assert padded == (0, 0, 150, 150)

    def test_pad_bbox_clips_to_bottom_right(self):
        ext = WallLineExtractor(detector=FakeDetector([]), padding_px=100)
        padded = ext._pad_bbox((150, 150, 200, 200), (200, 200))
        assert padded == (50, 50, 200, 200)


class TestPointInBox:
    def test_inside(self):
        assert WallLineExtractor._point_in_box((50, 50), (0, 0, 100, 100))

    def test_outside(self):
        assert not WallLineExtractor._point_in_box((150, 50), (0, 0, 100, 100))

    def test_on_edge_counts_as_inside(self):
        assert WallLineExtractor._point_in_box((100, 100), (0, 0, 100, 100))


class TestThreeChannelInput:
    def test_color_image_handled_for_wall_region(self):
        # Grayscale grid → BGR → ensure extractor still works.
        bgr = cv2.cvtColor(_grid_image(), cv2.COLOR_GRAY2BGR)
        ext = WallLineExtractor(
            detector=FakeDetector([_det("wall", (0, 0, 400, 400))])
        )
        segments = ext.extract(bgr)
        assert len(segments) > 0


class TestZeroSizeCrop:
    def test_zero_size_crop_returns_empty(self):
        # Wall bbox of zero area — padded crop is empty after clipping.
        ext = WallLineExtractor(
            detector=FakeDetector([_det("wall", (50, 50, 50, 50))]),
            padding_px=0,
        )
        assert ext.extract(_grid_image()) == []


class TestLastDetectionsCache:
    def test_last_detections_starts_empty(self):
        ext = WallLineExtractor(detector=FakeDetector([]))
        assert ext.last_detections == []

    def test_extract_populates_last_detections(self):
        detections = [_det("wall", (0, 0, 400, 400)), _det("door", (100, 100, 150, 150))]
        ext = WallLineExtractor(detector=FakeDetector(detections))
        ext.extract(_grid_image())
        # last_detections is a list copy of what detector returned (both items)
        assert len(ext.last_detections) == 2
        assert ext.last_detections[0].label == "wall"
        assert ext.last_detections[1].label == "door"

    def test_consecutive_extract_calls_replace_cache(self):
        ext = WallLineExtractor(detector=FakeDetector([_det("wall", (0, 0, 400, 400))]))
        ext.extract(_grid_image())
        assert len(ext.last_detections) == 1
        # Now swap the detector's returned list for a new one (simulates
        # the next call returning different results)
        ext.detector = FakeDetector([])  # type: ignore[assignment]
        ext.extract(_grid_image())
        assert ext.last_detections == []


class TestProtocolConformance:
    def test_fake_detector_satisfies_protocol(self):
        # Static check: FakeDetector implements the YoloDetector contract.
        detector: YoloDetector = FakeDetector([])
        assert detector.detect(_grid_image()) == []
