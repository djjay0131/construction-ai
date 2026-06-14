"""Unit tests for ``app.core.parsers.raster_parser``.

Uses fake collaborators for everything that costs real I/O or CV.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from app.core.cv.image_preprocessor import SkewRejected
from app.core.cv.scale_detector import ScaleWarning
from app.core.parsers.raster_parser import RasterParseError, RasterParser


def _seg(p1, p2):
    return (tuple(p1), tuple(p2))


def _make_parser(
    *,
    image=None,
    preprocessor_run=None,
    extractor_segments=None,
    extractor_raises=None,
    scale_value=None,
    scale_raises=None,
):
    """Build a RasterParser with the requested fakes plugged in."""
    image = image if image is not None else np.zeros((100, 100), dtype=np.uint8)

    pre = MagicMock()
    if preprocessor_run is None:
        pre.run = MagicMock(return_value=image)
    else:
        pre.run = MagicMock(side_effect=preprocessor_run)

    ext = MagicMock()
    if extractor_raises:
        ext.extract = MagicMock(side_effect=extractor_raises)
    else:
        ext.extract = MagicMock(
            return_value=extractor_segments if extractor_segments is not None else []
        )

    scale = MagicMock()
    if scale_raises:
        scale.detect = MagicMock(side_effect=scale_raises)
    else:
        scale.detect = MagicMock(
            return_value=scale_value if scale_value is not None else 1.0
        )

    parser = RasterParser(
        file_path="/tmp/fake.png",
        preprocessor=pre,
        line_extractor=ext,
        scale_detector=scale,
        image_loader=lambda _p: image,
    )
    parser.image = image  # pre-load so we don't hit disk
    return parser


class TestDefaultImageLoader:
    def test_default_loader_reads_existing_png(self, tmp_path):
        # Write a tiny PNG to disk; default loader (cv2.imread) should read it.
        import cv2 as cv2_module

        img = np.full((4, 4), 200, dtype=np.uint8)
        png_path = tmp_path / "tiny.png"
        cv2_module.imwrite(str(png_path), img)

        parser = RasterParser(png_path)  # uses _default_image_loader
        assert parser.load() is True
        assert parser.image is not None
        assert parser.image.shape[:2] == (4, 4)


class TestConstructorDefaults:
    def test_constructs_with_minimum_args(self, tmp_path):
        # Real defaults: preprocessor + scale_detector spin up; extractor
        # is None and the parser must report that on extract.
        parser = RasterParser(tmp_path / "missing.png")
        assert parser.preprocessor is not None
        assert parser.scale_detector is not None
        assert parser.line_extractor is None


class TestLoad:
    def test_load_returns_true_when_loader_returns_image(self, tmp_path):
        img = np.zeros((10, 10), dtype=np.uint8)
        parser = RasterParser(tmp_path / "x.png", image_loader=lambda _p: img)
        assert parser.load() is True
        assert parser.image is img

    def test_load_returns_false_when_loader_returns_none(self, tmp_path):
        parser = RasterParser(tmp_path / "x.png", image_loader=lambda _p: None)
        assert parser.load() is False


class TestExtractWallsErrorPaths:
    def test_load_failure_raises(self, tmp_path):
        parser = RasterParser(tmp_path / "x.png", image_loader=lambda _p: None)
        with pytest.raises(RasterParseError, match="Could not load"):
            parser.extract_walls()

    def test_missing_line_extractor_raises(self, tmp_path):
        img = np.zeros((10, 10), dtype=np.uint8)
        parser = RasterParser(tmp_path / "x.png", image_loader=lambda _p: img)
        with pytest.raises(RasterParseError, match="line_extractor"):
            parser.extract_walls()

    def test_skewed_image_wraps_to_raster_parse_error(self):
        parser = _make_parser(
            preprocessor_run=SkewRejected("skewed by 12.5 degrees"),
        )
        with pytest.raises(RasterParseError, match="12.5"):
            parser.extract_walls()

    def test_no_walls_detected_raises(self):
        parser = _make_parser(extractor_segments=[])
        with pytest.raises(RasterParseError, match="No walls"):
            parser.extract_walls()


class TestExtractWallsScaleHandling:
    def test_scale_warning_returns_metadata_not_exception(self):
        parser = _make_parser(
            extractor_segments=[_seg((0, 0), (100, 0))],
            scale_raises=ScaleWarning("need manual_scale"),
        )
        walls, meta = parser.extract_walls()
        assert walls == []
        assert "scale_warning" in meta
        assert "manual_scale" in meta["scale_warning"]

    def test_manual_scale_passed_to_detector(self):
        parser = _make_parser(
            extractor_segments=[_seg((0, 0), (100, 0))],
            scale_value=2.0,
        )
        parser.extract_walls(manual_scale='1/4"=1\'-0"')
        kwargs = parser.scale_detector.detect.call_args.kwargs
        assert kwargs["manual_scale"] == '1/4"=1\'-0"'
        assert kwargs["reference"] is None

    def test_reference_passed_to_detector(self):
        parser = _make_parser(
            extractor_segments=[_seg((0, 0), (100, 0))],
            scale_value=2.0,
        )
        ref = {"wall_index": 0, "length_inches": 50}
        parser.extract_walls(reference_measurement=ref)
        kwargs = parser.scale_detector.detect.call_args.kwargs
        assert kwargs["reference"] is ref


class TestExtractWallsHappyPath:
    def test_returns_wall_elements_with_correct_scale(self):
        parser = _make_parser(
            extractor_segments=[
                _seg((0, 0), (100, 0)),
                _seg((100, 0), (100, 50)),
            ],
            scale_value=10.0,  # 10 px per inch
        )
        walls, meta = parser.extract_walls(manual_scale='1/4"=1\'-0"')
        assert meta == {}
        assert len(walls) == 2
        # Each wall length = pixel length / 10
        assert walls[0].length_inches == pytest.approx(10.0)
        assert walls[1].length_inches == pytest.approx(5.0)
