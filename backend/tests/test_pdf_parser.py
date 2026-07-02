"""Unit tests for the Sprint 4f PDF vector-parser rewrite.

Covers scale detection (manual + auto + fallback), scale-aware
length conversion, and the extended path-walking (`l` / `m` / `re` /
`qu` / `c` item shapes surfaced by the Vermont spike).

Path-walking tests drive ``_convert_path_to_walls`` directly with
synthetic item lists so they don't depend on which item shape PyMuPDF
happens to emit for a given drawing primitive — that variance is
exactly what Sprint 4f is fixing.
"""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from app.core.parsers.pdf_parser import (
    MIN_WALL_LENGTH_IN,
    PDFParser,
    PDFWallElement,
    SCALE_PATTERN,
    ScaleParseError,
    _parse_fraction,
    _parse_scale_string,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_pdf_with_text(tmp_path, text: str, name: str = "test.pdf") -> Path:
    """Build a 1-page PDF whose page-0 text contains ``text``."""
    path = tmp_path / name
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((50, 50), text)
    doc.save(str(path))
    doc.close()
    return path


def make_blank_pdf(tmp_path, name: str = "blank.pdf") -> Path:
    path = tmp_path / name
    doc = fitz.open()
    doc.new_page(width=612, height=792)
    doc.save(str(path))
    doc.close()
    return path


# ---------------------------------------------------------------------------
# AC-1: _parse_scale_string covers standard architectural scales
# ---------------------------------------------------------------------------


class TestParseScaleString:
    @pytest.mark.parametrize(
        "scale_str, expected",
        [
            ('1/4"=1\'-0"', 12.0 / (0.25 * 72)),   # ≈ 0.6667
            ('1/8"=1\'', 12.0 / (0.125 * 72)),      # ≈ 1.333
            ('3/16"=1\'', 12.0 / ((3 / 16) * 72)),
            ('1/2"=1\'', 12.0 / (0.5 * 72)),
            ('1"=1\'', 12.0 / (1.0 * 72)),
        ],
    )
    def test_standard_architectural_scales_produce_expected_in_per_pt(
        self, scale_str, expected,
    ):
        assert _parse_scale_string(scale_str) == pytest.approx(expected)

    def test_accepts_curly_quotes(self):
        # 1/4″ = 1'-0″
        got = _parse_scale_string("1/4″=1′")
        assert got == pytest.approx(12.0 / (0.25 * 72))

    def test_accepts_em_dash_separator(self):
        got = _parse_scale_string('1/4"—1\'')
        assert got == pytest.approx(12.0 / (0.25 * 72))

    def test_raises_on_unparseable(self):
        with pytest.raises(ScaleParseError):
            _parse_scale_string("gibberish")

    def test_raises_on_zero_drawn(self):
        with pytest.raises(ScaleParseError):
            _parse_scale_string('0"=1\'')


class TestParseFraction:
    @pytest.mark.parametrize(
        "s, expected",
        [("1/4", 0.25), ("0.25", 0.25), ("3", 3.0), ("3/16", 3 / 16)],
    )
    def test_common_forms(self, s, expected):
        assert _parse_fraction(s) == pytest.approx(expected)


# ---------------------------------------------------------------------------
# AC-2 / AC-3 / AC-4 / AC-5: scale-detection cascade
# ---------------------------------------------------------------------------


class TestScaleDetection:
    def test_auto_detected_scale_populates_source_and_no_warning(self, tmp_path):
        pdf = make_pdf_with_text(tmp_path, 'SCALE: 1/4"=1\'-0"')
        p = PDFParser(str(pdf))
        assert p.load()
        assert p.scale_source == "auto_text"
        assert p.scale_warning is None
        assert p.scale_in_per_pt == pytest.approx(12.0 / (0.25 * 72))

    def test_unknown_scale_populates_warning_and_falls_back_to_1_to_1(
        self, tmp_path,
    ):
        pdf = make_blank_pdf(tmp_path)
        p = PDFParser(str(pdf))
        assert p.load()
        assert p.scale_source == "unknown"
        assert p.scale_warning is not None
        assert "manual_scale" in p.scale_warning
        assert p.scale_in_per_pt == pytest.approx(1.0 / 72.0)

    def test_manual_override_beats_auto_detect(self, tmp_path):
        pdf = make_pdf_with_text(tmp_path, 'SCALE: 1/8"=1\'-0"')
        p = PDFParser(str(pdf), manual_scale='1/4"=1\'-0"')
        assert p.load()
        assert p.scale_source == "manual"
        assert p.scale_in_per_pt == pytest.approx(12.0 / (0.25 * 72))

    def test_malformed_manual_falls_through_to_auto(self, tmp_path):
        pdf = make_pdf_with_text(tmp_path, 'SCALE: 1/4"=1\'-0"')
        p = PDFParser(str(pdf), manual_scale="not-a-scale-string")
        assert p.load()
        assert p.scale_source == "auto_text"

    def test_malformed_manual_and_no_text_falls_to_unknown(self, tmp_path):
        pdf = make_blank_pdf(tmp_path)
        p = PDFParser(str(pdf), manual_scale="not-a-scale-string")
        assert p.load()
        assert p.scale_source == "unknown"

    def test_load_returns_false_on_missing_file(self):
        p = PDFParser("/nope/does-not-exist.pdf")
        assert not p.load()

    def test_extract_walls_returns_empty_without_load(self):
        p = PDFParser("/some/path.pdf")
        assert p.extract_walls() == []


class TestScalePatternRegexHitsRealVariants:
    """Regression guard on the broadened SCALE_PATTERN regex."""

    @pytest.mark.parametrize(
        "text",
        [
            'SCALE: 1/4"=1\'-0"',            # canonical
            'Scale: 1/4"=1\'',                # sentence case, no "-0"
            'SCALE  1/4"=1\'',                # multi-space, no colon
            '1/4"=1\'-0"',                    # bare ratio (no SCALE prefix)
            '1/4"=1\'',                       # bare, no "-0"
            '1/4″=1′',              # curly quotes
            '1/4"—1\'',                       # em-dash separator
            'scale: 1/8"=1\'-0"',             # lowercase
        ],
    )
    def test_pattern_matches_real_world_variants(self, text):
        assert SCALE_PATTERN.search(text) is not None


# ---------------------------------------------------------------------------
# AC-12: PDFWallElement.length_inches honors scale_in_per_pt
# ---------------------------------------------------------------------------


class TestPDFWallElementLengthInches:
    def test_length_inches_uses_injected_scale(self):
        # 36-pt horizontal wall at 1/4"=1'-0" → 24 real inches (= 2 ft)
        w = PDFWallElement(
            start_point=(0, 0),
            end_point=(36, 0),
            scale_in_per_pt=12.0 / (0.25 * 72),
        )
        assert w.length_inches == pytest.approx(24.0)

    def test_length_inches_falls_back_to_1_to_1_by_default(self):
        # 72-pt horizontal wall at default 1:1 → 1 real inch
        w = PDFWallElement(start_point=(0, 0), end_point=(72, 0))
        assert w.length_inches == pytest.approx(1.0)

    def test_length_property_is_raw_pdf_points(self):
        w = PDFWallElement(
            start_point=(0, 0),
            end_point=(3, 4),  # 3-4-5 right triangle → 5 pts
            scale_in_per_pt=12.0 / (0.25 * 72),
        )
        assert w.length == pytest.approx(5.0)

    def test_repr_includes_scaled_length(self):
        w = PDFWallElement(
            start_point=(0, 0), end_point=(72, 0),
            scale_in_per_pt=1 / 72.0,
        )
        assert "length_in=1.00" in repr(w)


# ---------------------------------------------------------------------------
# AC-6 / AC-7 / AC-8 / AC-9 / AC-10 / AC-14: path-walking item shapes
# ---------------------------------------------------------------------------


class _P:
    """Minimal fitz.Point stand-in for synthetic item lists."""

    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)


class _Rect:
    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1


class _Quad:
    def __init__(self, ul, ur, ll, lr):
        self.ul, self.ur, self.ll, self.lr = ul, ur, ll, lr


def _walker():
    """Build a PDFParser without loading a doc, ready for path walking."""
    p = PDFParser("/fake/path.pdf")
    # 1:1 scale (default) so raw PDF distance == length_inches ÷ 72
    return p


class TestPathWalkingExplicitLine:
    """AC-6: ('l', p1, p2) explicit lines (newer PyMuPDF; Vermont)."""

    def test_produces_one_wall_per_explicit_line(self):
        parser = _walker()
        items = [("l", _P(0, 0), _P(100, 0)), ("l", _P(100, 0), _P(100, 100))]
        walls = parser._convert_path_to_walls(items, page_num=0)
        assert len(walls) == 2
        assert walls[0].start_point == (0.0, 0.0)
        assert walls[0].end_point == (100.0, 0.0)


class TestPathWalkingMoveThenLine:
    """AC-7: ('m', p); ('l', p) sequences (older PyMuPDF)."""

    def test_move_then_line_produces_wall(self):
        parser = _walker()
        items = [("m", _P(10, 10)), ("l", _P(110, 10))]
        walls = parser._convert_path_to_walls(items, page_num=0)
        assert len(walls) == 1
        assert walls[0].start_point == (10.0, 10.0)
        assert walls[0].end_point == (110.0, 10.0)

    def test_current_point_advances_across_multiple_lines(self):
        parser = _walker()
        items = [
            ("m", _P(0, 0)),
            ("l", _P(100, 0)),
            ("l", _P(100, 100)),
            ("l", _P(0, 100)),
        ]
        walls = parser._convert_path_to_walls(items, page_num=0)
        assert len(walls) == 3
        assert walls[-1].start_point == (100.0, 100.0)
        assert walls[-1].end_point == (0.0, 100.0)


class TestPathWalkingRectangle:
    """AC-8: ('re', Rect) unpacks into 4 perimeter walls."""

    def test_rectangle_produces_four_walls(self):
        parser = _walker()
        items = [("re", _Rect(0, 0, 100, 50))]
        walls = parser._convert_path_to_walls(items, page_num=0)
        assert len(walls) == 4
        # Perimeter walls form a closed loop
        endpoints = [(w.start_point, w.end_point) for w in walls]
        assert endpoints[0] == ((0.0, 0.0), (100.0, 0.0))
        assert endpoints[-1][1] == endpoints[0][0]  # closes the loop


class TestPathWalkingQuad:
    """AC-14: ('qu', Quad) unpacks into 4 walls (Vermont uses this)."""

    def test_quad_produces_four_walls(self):
        parser = _walker()
        quad = _Quad(
            ul=_P(0, 0), ur=_P(100, 0),
            ll=_P(0, 50), lr=_P(100, 50),
        )
        items = [("qu", quad)]
        walls = parser._convert_path_to_walls(items, page_num=0)
        assert len(walls) == 4
        # First wall: ul → ur; last wall: ll → ul (closing back)
        assert walls[0].start_point == (0.0, 0.0)
        assert walls[0].end_point == (100.0, 0.0)
        assert walls[-1].end_point == (0.0, 0.0)


class TestPathWalkingLonelyLine:
    """AC-9: ('l', p) with no prior ('m', *) is skipped."""

    def test_line_without_move_produces_no_wall(self):
        parser = _walker()
        items = [("l", _P(100, 100))]
        walls = parser._convert_path_to_walls(items, page_num=0)
        assert walls == []

    def test_line_without_move_then_move_recovers(self):
        parser = _walker()
        items = [
            ("l", _P(100, 100)),   # skipped
            ("m", _P(0, 0)),
            ("l", _P(50, 0)),      # produces a wall
        ]
        walls = parser._convert_path_to_walls(items, page_num=0)
        assert len(walls) == 1
        assert walls[0].start_point == (0.0, 0.0)


class TestPathWalkingCubicBezier:
    """AC-10: ('c', ...) skipped as wall; advances current_point to end."""

    def test_curve_produces_no_wall_but_advances_current_point(self):
        parser = _walker()
        items = [
            ("m", _P(0, 0)),
            ("c", _P(10, 10), _P(20, 20), _P(30, 30), _P(100, 100)),
            ("l", _P(200, 100)),  # anchored to curve end (100, 100)
        ]
        walls = parser._convert_path_to_walls(items, page_num=0)
        assert len(walls) == 1
        assert walls[0].start_point == (100.0, 100.0)
        assert walls[0].end_point == (200.0, 100.0)

    def test_bare_curve_command_falls_through(self):
        # Defensive: cmd == "c" with no points at all (never observed in
        # real PDFs, but guard exists).
        parser = _walker()
        items = [("c",)]
        walls = parser._convert_path_to_walls(items, page_num=0)
        assert walls == []


class TestPathWalkingUnknownCommand:
    def test_unknown_command_silently_skipped(self):
        parser = _walker()
        items = [("mystery",)]
        walls = parser._convert_path_to_walls(items, page_num=0)
        assert walls == []


class TestPtNormalizer:
    def test_normalizes_fitz_point(self):
        assert PDFParser._pt(_P(3, 4)) == (3.0, 4.0)

    def test_normalizes_plain_tuple(self):
        assert PDFParser._pt((3, 4)) == (3.0, 4.0)


# ---------------------------------------------------------------------------
# AC-11: length filter at boundary
# ---------------------------------------------------------------------------


class _FakePage:
    """Stand-in for fitz.Page — only needs get_drawings() for the filter test."""

    def __init__(self, drawings):
        self._drawings = drawings

    def get_drawings(self):
        return self._drawings


class TestLengthFilter:
    @pytest.mark.parametrize("length_in, kept", [
        (0.99, False),
        (1.00, True),
        (1.01, True),
        (100.0, True),
    ])
    def test_filter_at_boundary(self, length_in, kept):
        parser = _walker()  # scale defaults to 1:1 (1/72 in per pt)
        # At 1:1 scale, a wall of length_in inches has length_in * 72 pts.
        pts = length_in * 72.0
        page = _FakePage([{"items": [("l", _P(0, 0), _P(pts, 0))]}])
        walls = parser._extract_walls_from_page(page, page_num=0)
        if kept:
            assert len(walls) == 1
            assert walls[0].length_inches == pytest.approx(length_in)
        else:
            assert walls == []

    def test_empty_path_items_skipped(self):
        parser = _walker()
        page = _FakePage([{"items": []}])
        assert parser._extract_walls_from_page(page, page_num=0) == []


# ---------------------------------------------------------------------------
# AC-13: run_pdf_takeoff threads manual_scale into PDFParser
# ---------------------------------------------------------------------------


class TestRunPdfTakeoffWiring:
    def test_manual_scale_reaches_pdf_parser(self, tmp_path, monkeypatch):
        from app.core.pdf_takeoff import run_pdf_takeoff
        from unittest.mock import MagicMock

        pdf = make_blank_pdf(tmp_path)

        # Capture the manual_scale passed into PDFParser.
        captured = {}
        real_ctor = PDFParser.__init__

        def spy(self, file_path, manual_scale=None):
            captured["manual_scale"] = manual_scale
            real_ctor(self, file_path, manual_scale=manual_scale)

        monkeypatch.setattr(PDFParser, "__init__", spy)

        run_pdf_takeoff(
            str(pdf),
            takeoff_id=1,
            upload_dir=tmp_path,
            ocr_reader=MagicMock(),
            line_extractor_factory=lambda: MagicMock(),
            dpi=200,
            manual_scale='1/4"=1\'-0"',
        )

        assert captured["manual_scale"] == '1/4"=1\'-0"'


# ---------------------------------------------------------------------------
# AC-15: Vermont produces walls > 0
# ---------------------------------------------------------------------------


VERMONT = Path(__file__).resolve().parent / "fixtures" / "phase1" / "vector_pdf_vermont.pdf"


@pytest.mark.skipif(not VERMONT.exists(), reason="Vermont fixture not bundled")
class TestVermontActivation:
    def test_vermont_produces_walls(self):
        p = PDFParser(str(VERMONT))
        assert p.load()
        walls = p.extract_walls()
        assert len(walls) > 0, "Vermont should produce > 0 walls after Sprint 4f"
        p.close()

    def test_vermont_has_no_scale_annotation_so_warning_populates(self):
        p = PDFParser(str(VERMONT))
        assert p.load()
        assert p.scale_source == "unknown"
        assert p.scale_warning is not None
        p.close()


# ---------------------------------------------------------------------------
# Misc: get_drawing_info / extract_text / close
# ---------------------------------------------------------------------------


class TestAncillaryAccessors:
    def test_get_drawing_info_returns_empty_before_load(self):
        p = PDFParser("/nope.pdf")
        assert p.get_drawing_info() == {}

    def test_get_drawing_info_after_load_reports_scale_source(self, tmp_path):
        pdf = make_pdf_with_text(tmp_path, 'SCALE: 1/4"=1\'-0"')
        p = PDFParser(str(pdf))
        assert p.load()
        info = p.get_drawing_info()
        assert info["scale_source"] == "auto_text"
        assert info["scale_warning"] is None
        assert info["page_count"] == 1

    def test_extract_text_returns_empty_without_load(self):
        p = PDFParser("/nope.pdf")
        assert p.extract_text() == []

    def test_extract_text_returns_text_blocks(self, tmp_path):
        pdf = make_pdf_with_text(tmp_path, "hello world")
        p = PDFParser(str(pdf))
        assert p.load()
        texts = p.extract_text()
        assert any("hello world" in t["text"] for t in texts)

    def test_extract_text_skips_out_of_range_pages(self, tmp_path):
        pdf = make_blank_pdf(tmp_path)
        p = PDFParser(str(pdf))
        assert p.load()
        assert p.extract_text(page_numbers=[5]) == []

    def test_extract_walls_skips_out_of_range_pages(self, tmp_path):
        pdf = make_blank_pdf(tmp_path)
        p = PDFParser(str(pdf))
        assert p.load()
        assert p.extract_walls(page_numbers=[5]) == []

    def test_extract_walls_all_pages_when_page_numbers_none(self, tmp_path):
        pdf = make_blank_pdf(tmp_path)
        p = PDFParser(str(pdf))
        assert p.load()
        # Blank page → no drawings → empty walls list, no crash.
        assert p.extract_walls() == []

    def test_close_after_load_is_idempotent_ish(self, tmp_path):
        pdf = make_blank_pdf(tmp_path)
        p = PDFParser(str(pdf))
        p.load()
        p.close()
        assert p.doc is None
        # second close on empty doc is a no-op
        p.close()


class TestMinWallLengthConstant:
    def test_default_is_one_inch(self):
        assert MIN_WALL_LENGTH_IN == 1.0
