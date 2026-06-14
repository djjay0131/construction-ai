"""Unit tests for ``app.core.cv.dimension_parser``."""

from __future__ import annotations

import pytest

from app.core.cv.dimension_parser import (
    DimensionParseError,
    DimensionParser,
    parse_dimension,
)


class TestEmptyInput:
    @pytest.mark.parametrize("bad", ["", "   ", "\t\n"])
    def test_empty_strings_raise(self, bad):
        with pytest.raises(DimensionParseError, match="empty dimension"):
            parse_dimension(bad)

    def test_none_raises(self):
        with pytest.raises(DimensionParseError, match="empty dimension"):
            parse_dimension(None)  # type: ignore[arg-type]

    def test_non_string_raises(self):
        with pytest.raises(DimensionParseError, match="empty dimension"):
            parse_dimension(12)  # type: ignore[arg-type]


class TestImperialFtIn:
    @pytest.mark.parametrize(
        "text, expected_in",
        [
            ('12\'-6"', 150.0),
            ("12'-6", 150.0),       # quote optional after the inches
            ("12'", 144.0),
            ("0'", 0.0),
            ('24\'-0"', 288.0),
            ("1'-1", 13.0),
            ('100\'-11"', 1211.0),
        ],
    )
    def test_imperial_ft_in_parses(self, text, expected_in):
        assert parse_dimension(text) == pytest.approx(expected_in)


class TestImperialFractional:
    @pytest.mark.parametrize(
        "text, expected_in",
        [
            ('12\'-6 1/2"', 150.5),
            ('12\'-6 1/4"', 150.25),
            ('0\'-6 1/2"', 6.5),
            ('1\'-0 3/4"', 12.75),
        ],
    )
    def test_imperial_fractional_parses(self, text, expected_in):
        assert parse_dimension(text) == pytest.approx(expected_in)


class TestInchesOnly:
    @pytest.mark.parametrize(
        "text, expected_in",
        [
            ('36"', 36.0),
            ("36 in", 36.0),
            ('6 1/2"', 6.5),
            ("6 1/2 in", 6.5),
            ('0"', 0.0),
        ],
    )
    def test_inches_only_parses(self, text, expected_in):
        assert parse_dimension(text) == pytest.approx(expected_in)


class TestImperialWords:
    @pytest.mark.parametrize(
        "text, expected_in",
        [
            ("12 ft 6 in", 150.0),
            ("24 ft", 288.0),
            ("12 FT 6 IN", 150.0),  # case-insensitive
            ("0 ft", 0.0),
        ],
    )
    def test_imperial_words_parses(self, text, expected_in):
        assert parse_dimension(text) == pytest.approx(expected_in)


class TestMetric:
    def test_mm_parses(self):
        # 3600 mm / 25.4 ≈ 141.732
        assert parse_dimension("3600mm") == pytest.approx(141.732, abs=0.01)

    def test_mm_with_space(self):
        assert parse_dimension("3600 mm") == pytest.approx(141.732, abs=0.01)

    def test_mm_uppercase(self):
        assert parse_dimension("3600MM") == pytest.approx(141.732, abs=0.01)

    def test_m_parses(self):
        # 3.6 m / 0.0254 ≈ 141.732
        assert parse_dimension("3.6m") == pytest.approx(141.732, abs=0.01)

    def test_small_m_parses(self):
        assert parse_dimension("914mm") == pytest.approx(35.984, abs=0.01)

    def test_mm_and_m_agree(self):
        # 3.6 m and 3600 mm are the same length; verify both parse to the
        # same number within 0.01 in.
        assert parse_dimension("3.6m") == pytest.approx(
            parse_dimension("3600mm"), abs=0.01
        )

    def test_decimal_metres(self):
        assert parse_dimension("2.5m") == pytest.approx(98.425, abs=0.01)


class TestGarbageStrings:
    @pytest.mark.parametrize(
        "bad",
        [
            "random text",
            "twelve feet",
            "---",
            "12 ' 6\" extra",  # trailing junk
            "ft 6 in",         # missing leading number
            "12'-",            # truncated
            'abc"',
        ],
    )
    def test_garbage_raises(self, bad):
        with pytest.raises(DimensionParseError, match="unrecognised"):
            parse_dimension(bad)


class TestZeroDenominator:
    def test_zero_denominator_in_inches_raises(self):
        with pytest.raises(DimensionParseError, match="zero denominator"):
            parse_dimension('6 1/0"')

    def test_zero_denominator_in_ft_in_raises(self):
        with pytest.raises(DimensionParseError, match="zero denominator"):
            parse_dimension('1\'-6 1/0"')


class TestDimensionParserClass:
    def test_parse_delegates_to_parse_dimension(self):
        p = DimensionParser()
        assert p.parse('12\'-6"') == pytest.approx(150.0)

    def test_parse_many_keeps_only_successes(self):
        p = DimensionParser()
        out = p.parse_many(['12\'-6"', "garbage", "24'", "more garbage", '36"'])
        assert out == [
            ('12\'-6"', 150.0),
            ("24'", 288.0),
            ('36"', 36.0),
        ]

    def test_parse_many_returns_empty_for_all_garbage(self):
        assert DimensionParser().parse_many(["a", "b", "c"]) == []

    def test_parse_many_returns_empty_for_empty_input(self):
        assert DimensionParser().parse_many([]) == []

    def test_parse_many_consumes_generator(self):
        out = DimensionParser().parse_many(t for t in ['12\'', '24"'])
        assert len(out) == 2
