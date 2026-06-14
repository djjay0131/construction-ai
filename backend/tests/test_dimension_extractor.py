"""Unit tests for ``app.core.cv.dimension_extractor``.

Uses a fake ``OcrReader`` so the test suite doesn't load EasyOCR.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.core.cv.dimension_extractor import (
    DimensionExtractor,
    OcrReader,
    ParsedDimension,
    TextBox,
)
from app.core.cv.dimension_parser import DimensionParser


class FakeReader:
    """Test-only OCR reader: returns whatever it was constructed with."""

    def __init__(self, text_boxes: list[TextBox]) -> None:
        self._text_boxes = list(text_boxes)
        self.calls: list = []

    def readtext(self, image) -> list[TextBox]:
        self.calls.append(image)
        return self._text_boxes


def _tb(text: str, bbox=(0, 0, 10, 10), confidence=0.9) -> TextBox:
    return TextBox(text=text, bbox=bbox, confidence=confidence)


@pytest.fixture
def dummy_image():
    return np.zeros((100, 100), dtype=np.uint8)


class TestProtocolConformance:
    def test_fake_reader_satisfies_protocol(self):
        reader: OcrReader = FakeReader([])
        assert reader.readtext(None) == []


class TestEmptyReaderResult:
    def test_extract_returns_empty_lists(self, dummy_image):
        ext = DimensionExtractor(reader=FakeReader([]))
        parsed, raw = ext.extract(dummy_image)
        assert parsed == []
        assert raw == []


class TestAllGarbageText:
    def test_parsed_empty_raw_has_everything(self, dummy_image):
        reader = FakeReader(
            [
                _tb("KITCHEN"),
                _tb("MASTER BEDROOM"),
                _tb("---"),
            ]
        )
        ext = DimensionExtractor(reader=reader)
        parsed, raw = ext.extract(dummy_image)
        assert parsed == []
        assert len(raw) == 3
        assert raw[0].text == "KITCHEN"


class TestMixedTextBoxes:
    def test_separates_dimensions_from_labels(self, dummy_image):
        # 2 dimensions, 1 room name, 1 garbage.
        reader = FakeReader(
            [
                _tb('12\'-6"', bbox=(10, 10, 60, 25), confidence=0.95),
                _tb("BATHROOM", bbox=(70, 30, 150, 50), confidence=0.88),
                _tb('24"', bbox=(0, 60, 30, 75), confidence=0.91),
                _tb("---", bbox=(80, 80, 90, 90), confidence=0.40),
            ]
        )
        ext = DimensionExtractor(reader=reader)
        parsed, raw = ext.extract(dummy_image)

        # 4 raw entries preserved
        assert len(raw) == 4
        # 2 parseable dimensions
        assert len(parsed) == 2

        # Bbox + confidence preserved on parsed entries
        assert parsed[0].text == '12\'-6"'
        assert parsed[0].bbox == (10, 10, 60, 25)
        assert parsed[0].confidence == 0.95
        assert parsed[0].inches == pytest.approx(150.0)

        assert parsed[1].text == '24"'
        assert parsed[1].bbox == (0, 60, 30, 75)
        assert parsed[1].inches == pytest.approx(24.0)


class TestParserInjection:
    def test_default_parser_used_when_omitted(self, dummy_image):
        ext = DimensionExtractor(reader=FakeReader([_tb('12\'-6"')]))
        parsed, _ = ext.extract(dummy_image)
        assert parsed[0].inches == pytest.approx(150.0)

    def test_custom_parser_used_when_provided(self, dummy_image):
        custom = DimensionParser()  # same behaviour for AC; tests the path
        ext = DimensionExtractor(
            reader=FakeReader([_tb('36"')]), parser=custom
        )
        parsed, _ = ext.extract(dummy_image)
        assert parsed[0].inches == pytest.approx(36.0)
        # Confirm the injected parser instance is the one held
        assert ext.parser is custom


class TestReaderInvocation:
    def test_image_passed_through_to_reader(self, dummy_image):
        reader = FakeReader([])
        ext = DimensionExtractor(reader=reader)
        ext.extract(dummy_image)
        assert len(reader.calls) == 1
        assert reader.calls[0] is dummy_image


class TestDataclassImmutability:
    def test_parsed_dimension_is_frozen(self):
        pd = ParsedDimension(
            text='12\'-6"', bbox=(0, 0, 10, 10), inches=150.0, confidence=0.9
        )
        with pytest.raises(AttributeError):
            pd.inches = 999.0  # type: ignore[misc]

    def test_text_box_is_frozen(self):
        tb = _tb("KITCHEN")
        with pytest.raises(AttributeError):
            tb.text = "different"  # type: ignore[misc]
