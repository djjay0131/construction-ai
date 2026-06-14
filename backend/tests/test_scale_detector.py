"""Unit tests for ``app.core.cv.scale_detector``."""

from __future__ import annotations

import numpy as np
import pytest

from app.core.cv.scale_detector import (
    PAPER_DPI,
    ScaleDetector,
    ScaleWarning,
    parse_manual_scale,
)


def _seg(p1, p2):
    return (tuple(p1), tuple(p2))


@pytest.fixture
def dummy_image():
    return np.zeros((400, 400), dtype=np.uint8)


class TestParseManualScale:
    @pytest.mark.parametrize(
        "text, expected_px_per_in",
        [
            # 1/4" = 1'-0" : 1/4 paper inch = 12 real inches.
            # paper_px = 0.25 * 96 = 24; scale = 24/12 = 2.0
            ('1/4"=1\'-0"', 2.0),
            # 1/8" = 1'-0" : 1/8 * 96 = 12; scale = 12/12 = 1.0
            ('1/8"=1\'-0"', 1.0),
            # 1" = 1'-0" : 96 / 12 = 8.0
            ('1"=1\'-0"', 8.0),
            # 1/2" = 1'-0" : 0.5 * 96 = 48; scale = 48/12 = 4.0
            ('1/2"=1\'-0"', 4.0),
        ],
    )
    def test_canonical_formats_parse(self, text, expected_px_per_in):
        assert parse_manual_scale(text) == pytest.approx(expected_px_per_in)

    def test_with_inches_in_real_measurement(self):
        # 1" = 1'-6" : 96 / 18 = 5.333...
        assert parse_manual_scale('1"=1\'-6"') == pytest.approx(96.0 / 18.0)

    @pytest.mark.parametrize(
        "bad",
        [
            "",
            "   ",
            "not a scale",
            "1/0\"=1'-0\"",          # zero denominator → 0 paper_in
            "1/4\"=0'-0\"",          # zero real inches
            "1/4=1'",                # missing quote on the paper side
        ],
    )
    def test_invalid_formats_raise(self, bad):
        with pytest.raises(ScaleWarning):
            parse_manual_scale(bad)

    def test_non_string_raises(self):
        with pytest.raises(ScaleWarning):
            parse_manual_scale(None)  # type: ignore[arg-type]


class TestConstructorValidation:
    def test_non_positive_min_raises(self):
        with pytest.raises(ValueError, match="positive"):
            ScaleDetector(min_wall_in=0)

    def test_max_below_min_raises(self):
        with pytest.raises(ValueError, match="must exceed min"):
            ScaleDetector(min_wall_in=10, max_wall_in=5)


class TestNoOverrides:
    def test_neither_manual_nor_reference_raises_with_instructions(
        self, dummy_image
    ):
        det = ScaleDetector()
        segs = [_seg((0, 0), (100, 0))]
        with pytest.raises(ScaleWarning) as exc:
            det.detect(dummy_image, segs)
        msg = str(exc.value)
        assert "manual_scale" in msg
        assert "reference_measurement" in msg


class TestReferenceCascade:
    def test_reference_succeeds(self, dummy_image):
        det = ScaleDetector()
        segs = [_seg((0, 0), (100, 0))]  # 100 px wall
        # Caller says that's 50 inches → scale = 100/50 = 2 px/in
        scale = det.detect(
            dummy_image, segs, reference={"wall_index": 0, "length_inches": 50}
        )
        assert scale == pytest.approx(2.0)

    def test_reference_missing_keys_raises(self, dummy_image):
        det = ScaleDetector()
        segs = [_seg((0, 0), (100, 0))]
        with pytest.raises(ScaleWarning, match="wall_index"):
            det.detect(dummy_image, segs, reference={"length_inches": 50})

    def test_reference_non_positive_length_raises(self, dummy_image):
        det = ScaleDetector()
        segs = [_seg((0, 0), (100, 0))]
        with pytest.raises(ScaleWarning, match="positive"):
            det.detect(
                dummy_image,
                segs,
                reference={"wall_index": 0, "length_inches": 0},
            )

    def test_reference_index_out_of_range_raises(self, dummy_image):
        det = ScaleDetector()
        segs = [_seg((0, 0), (100, 0))]
        with pytest.raises(ScaleWarning, match="out of range"):
            det.detect(
                dummy_image,
                segs,
                reference={"wall_index": 5, "length_inches": 50},
            )

    def test_reference_zero_pixel_length_raises(self, dummy_image):
        det = ScaleDetector()
        # Segment with zero length
        segs = [_seg((100, 100), (100, 100))]
        with pytest.raises(ScaleWarning, match="zero pixel length"):
            det.detect(
                dummy_image,
                segs,
                reference={"wall_index": 0, "length_inches": 50},
            )

    def test_reference_bad_types_raises(self, dummy_image):
        det = ScaleDetector()
        segs = [_seg((0, 0), (100, 0))]
        with pytest.raises(ScaleWarning, match="reference must have"):
            det.detect(
                dummy_image,
                segs,
                reference={"wall_index": "abc", "length_inches": 50},
            )


class TestManualScaleCascade:
    def test_manual_scale_resolves_and_passes_plausibility(self, dummy_image):
        det = ScaleDetector()
        # Wall 100 px; manual "1/4"=1'-0"" → scale = 2 px/in.
        # 100 px / 2 px-per-in = 50 inches → within [24, 960].
        segs = [_seg((0, 0), (100, 0))]
        scale = det.detect(dummy_image, segs, manual_scale='1/4"=1\'-0"')
        assert scale == pytest.approx(2.0)


class TestPlausibilityCheck:
    def test_wall_too_small_raises(self, dummy_image):
        det = ScaleDetector()
        # 100 px wall, manual_scale = "1"=1'-0"" → 8 px/in → 12.5 inches.
        # 12.5 in < 24 in min → ScaleWarning.
        segs = [_seg((0, 0), (100, 0))]
        with pytest.raises(ScaleWarning, match="Plausibility check failed"):
            det.detect(dummy_image, segs, manual_scale='1"=1\'-0"')

    def test_wall_too_large_raises(self, dummy_image):
        det = ScaleDetector()
        # 10000 px wall, manual_scale = "1/4"=1'-0"" → 2 px/in → 5000 in
        # 5000 in > 960 in max → ScaleWarning.
        segs = [_seg((0, 0), (10000, 0))]
        with pytest.raises(ScaleWarning, match="Plausibility check failed"):
            det.detect(dummy_image, segs, manual_scale='1/4"=1\'-0"')

    def test_message_names_offending_segment_index(self, dummy_image):
        det = ScaleDetector()
        segs = [
            _seg((0, 0), (100, 0)),     # OK (50 in)
            _seg((0, 100), (10000, 100)),  # Too big
        ]
        with pytest.raises(ScaleWarning) as exc:
            det.detect(dummy_image, segs, manual_scale='1/4"=1\'-0"')
        assert "segment 1" in str(exc.value)


class TestPaperDpiAssumption:
    def test_paper_dpi_is_96(self):
        # Lock the assumption — if anyone wants to change DPI they have to
        # update tests too.
        assert PAPER_DPI == 96.0
