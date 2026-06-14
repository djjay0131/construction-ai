"""Unit tests for ``app.core.cv.image_preprocessor``.

All inputs are synthetic numpy arrays — no real scanned plans needed.
The skew-detection algorithm is exercised by feeding pre-drawn grids
rotated by known angles via ``cv2.warpAffine``.
"""

from __future__ import annotations

from unittest.mock import patch

import cv2
import numpy as np
import pytest

from app.core.cv.image_preprocessor import ImagePreprocessor, SkewRejected


def _grid_image(angle_deg: float = 0.0, size: int = 600) -> np.ndarray:
    """Build a white image with a grid of black lines, then rotate by ``angle_deg``."""
    img = np.full((size, size), 255, dtype=np.uint8)
    # Horizontal + vertical lines so Hough finds plenty of edges.
    for y in range(50, size, 50):
        cv2.line(img, (0, y), (size, y), 0, thickness=2)
    for x in range(50, size, 50):
        cv2.line(img, (x, 0), (x, size), 0, thickness=2)

    if angle_deg != 0.0:
        center = (size / 2, size / 2)
        rot = cv2.getRotationMatrix2D(center, angle_deg, 1.0)
        img = cv2.warpAffine(img, rot, (size, size), borderValue=255)
    return img


class TestConstructorValidation:
    def test_zero_threshold_raises(self):
        with pytest.raises(ValueError, match="positive"):
            ImagePreprocessor(skew_threshold_deg=0)

    def test_negative_threshold_raises(self):
        with pytest.raises(ValueError, match="positive"):
            ImagePreprocessor(skew_threshold_deg=-1.0)


class TestDetectSkewInputValidation:
    def test_none_image_raises_value_error(self):
        with pytest.raises(ValueError, match="empty image"):
            ImagePreprocessor().detect_skew(None)

    def test_zero_size_array_raises_value_error(self):
        with pytest.raises(ValueError, match="empty image"):
            ImagePreprocessor().detect_skew(np.zeros((0, 0), dtype=np.uint8))


class TestDetectSkewSyntheticInputs:
    def test_unskewed_grid_returns_near_zero(self):
        skew = ImagePreprocessor().detect_skew(_grid_image(angle_deg=0.0))
        assert abs(skew) < 1.0

    def test_blank_image_returns_zero(self):
        blank = np.full((400, 400), 200, dtype=np.uint8)
        assert ImagePreprocessor().detect_skew(blank) == 0.0

    def test_three_channel_image_handled(self):
        # Color (BGR) grid — preprocessor must downconvert to grayscale.
        grid = _grid_image(angle_deg=0.0)
        bgr = cv2.cvtColor(grid, cv2.COLOR_GRAY2BGR)
        skew = ImagePreprocessor().detect_skew(bgr)
        assert abs(skew) < 1.0


class TestRunSkewGate:
    def test_run_accepts_clean_image(self):
        out = ImagePreprocessor().run(_grid_image(angle_deg=0.0))
        assert out is not None
        assert out.ndim == 2  # single-channel result
        assert out.dtype == np.uint8

    def test_run_rejects_when_skew_over_threshold(self):
        pre = ImagePreprocessor(skew_threshold_deg=5.0)
        # Mock detect_skew to bypass any noise from cv2 transforms.
        with patch.object(pre, "detect_skew", return_value=7.0):
            with pytest.raises(SkewRejected) as exc:
                pre.run(_grid_image())
        assert "7.0" in str(exc.value)
        assert "5.0" in str(exc.value)

    def test_run_accepts_exactly_at_threshold(self):
        pre = ImagePreprocessor(skew_threshold_deg=5.0)
        with patch.object(pre, "detect_skew", return_value=5.0):
            out = pre.run(_grid_image())
        assert out is not None  # 5.0 not > 5.0, so accepted

    def test_run_accepts_just_under_threshold(self):
        pre = ImagePreprocessor(skew_threshold_deg=5.0)
        with patch.object(pre, "detect_skew", return_value=4.99):
            out = pre.run(_grid_image())
        assert out is not None

    def test_run_rejects_just_over_threshold(self):
        pre = ImagePreprocessor(skew_threshold_deg=5.0)
        with patch.object(pre, "detect_skew", return_value=5.01):
            with pytest.raises(SkewRejected):
                pre.run(_grid_image())

    def test_run_rejects_negative_skew_over_threshold(self):
        pre = ImagePreprocessor(skew_threshold_deg=5.0)
        with patch.object(pre, "detect_skew", return_value=-6.0):
            with pytest.raises(SkewRejected) as exc:
                pre.run(_grid_image())
        assert "-6.0" in str(exc.value)

    def test_custom_threshold_respected(self):
        pre = ImagePreprocessor(skew_threshold_deg=2.0)
        with patch.object(pre, "detect_skew", return_value=3.0):
            with pytest.raises(SkewRejected):
                pre.run(_grid_image())


class TestRunOutputShape:
    def test_color_input_returns_single_channel(self):
        bgr = cv2.cvtColor(_grid_image(), cv2.COLOR_GRAY2BGR)
        out = ImagePreprocessor().run(bgr)
        assert out.ndim == 2
