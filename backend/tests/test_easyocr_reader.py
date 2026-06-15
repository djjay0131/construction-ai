"""Unit tests for ``app.core.cv.easyocr_reader``.

We don't load real EasyOCR — too heavy. Instead we patch
``easyocr.Reader`` to a `MagicMock` so the lazy-init contract is
testable in <1 s.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import numpy as np
import pytest

from app.core.cv.dimension_extractor import TextBox
from app.core.cv.easyocr_reader import EasyOcrReader


@pytest.fixture
def stub_easyocr(monkeypatch):
    """Install a fake ``easyocr`` module in ``sys.modules`` whose
    ``Reader(*args, **kw)`` returns a MagicMock with a ``.readtext`` method."""
    fake_module = types.ModuleType("easyocr")
    reader_mock = MagicMock()
    reader_mock.readtext.return_value = []
    reader_ctor = MagicMock(return_value=reader_mock)
    fake_module.Reader = reader_ctor  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "easyocr", fake_module)
    return reader_ctor, reader_mock


class TestLazyInit:
    def test_ctor_does_not_construct_easyocr_reader(self, stub_easyocr):
        ctor, _ = stub_easyocr
        EasyOcrReader()
        assert ctor.call_count == 0  # no eager init

    def test_readtext_constructs_reader_exactly_once(self, stub_easyocr):
        ctor, _ = stub_easyocr
        r = EasyOcrReader()
        img = np.zeros((10, 10), dtype=np.uint8)
        r.readtext(img)
        r.readtext(img)
        r.readtext(img)
        assert ctor.call_count == 1

    def test_languages_default_is_english(self, stub_easyocr):
        ctor, _ = stub_easyocr
        EasyOcrReader().readtext(np.zeros((10, 10), dtype=np.uint8))
        assert ctor.call_args.args[0] == ["en"]

    def test_languages_kwarg_forwarded(self, stub_easyocr):
        ctor, _ = stub_easyocr
        EasyOcrReader(languages=["en", "es"]).readtext(
            np.zeros((10, 10), dtype=np.uint8)
        )
        assert ctor.call_args.args[0] == ["en", "es"]

    def test_gpu_kwarg_forwarded(self, stub_easyocr):
        ctor, _ = stub_easyocr
        EasyOcrReader(gpu=True).readtext(np.zeros((10, 10), dtype=np.uint8))
        assert ctor.call_args.kwargs["gpu"] is True


class TestQuadToBboxConversion:
    def test_axis_aligned_quad(self, stub_easyocr):
        _, reader_mock = stub_easyocr
        reader_mock.readtext.return_value = [
            ([[10, 5], [60, 5], [60, 25], [10, 25]], "12'-6\"", 0.95),
        ]
        r = EasyOcrReader()
        out = r.readtext(np.zeros((10, 10), dtype=np.uint8))
        assert len(out) == 1
        tb = out[0]
        assert isinstance(tb, TextBox)
        assert tb.text == "12'-6\""
        assert tb.bbox == (10, 5, 60, 25)
        assert tb.confidence == 0.95

    def test_rotated_quad_becomes_axis_aligned_bbox(self, stub_easyocr):
        _, reader_mock = stub_easyocr
        # Rotated 45° square — min/max should give the encompassing bbox.
        reader_mock.readtext.return_value = [
            ([[50, 10], [90, 50], [50, 90], [10, 50]], "X", 0.7),
        ]
        r = EasyOcrReader()
        out = r.readtext(np.zeros((10, 10), dtype=np.uint8))
        assert out[0].bbox == (10, 10, 90, 90)

    def test_quad_with_float_points_is_cast_to_int(self, stub_easyocr):
        _, reader_mock = stub_easyocr
        reader_mock.readtext.return_value = [
            ([[10.7, 5.2], [60.4, 5.8], [60.1, 25.6], [10.3, 25.4]], "T", 0.5),
        ]
        r = EasyOcrReader()
        out = r.readtext(np.zeros((10, 10), dtype=np.uint8))
        # int() truncates, so 10.7→10, 60.4→60, 25.6→25
        assert out[0].bbox == (10, 5, 60, 25)


class TestEmptyResult:
    def test_empty_readtext_returns_empty_list(self, stub_easyocr):
        _, reader_mock = stub_easyocr
        reader_mock.readtext.return_value = []
        r = EasyOcrReader()
        assert r.readtext(np.zeros((10, 10), dtype=np.uint8)) == []


class TestProtocolConformance:
    def test_easyocr_reader_satisfies_ocr_reader_protocol(self, stub_easyocr):
        # Static contract: import-time check is satisfied via Protocol;
        # at runtime, plug into DimensionExtractor to confirm.
        from app.core.cv.dimension_extractor import DimensionExtractor

        ext = DimensionExtractor(reader=EasyOcrReader())
        parsed, raw = ext.extract(np.zeros((10, 10), dtype=np.uint8))
        assert parsed == [] and raw == []
