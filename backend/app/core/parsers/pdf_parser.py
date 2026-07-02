"""PDF Parser Module.

Parses PDF architectural drawings using PyMuPDF (fitz). Extracts vector
paths and converts them to wall geometry with real-world lengths.

Sprint 4f rewrite covers two stacked bugs surfaced by Sprint 5's
Vermont-Microhouse fixture:

* **Path-walking bug** — the pre-Sprint-4f parser only handled
  ``("m", p)`` / ``("l", p)`` move-then-line pairs. Real PDFs emit
  ``("l", p1, p2)`` explicit lines, ``("re", Rect)`` rectangles, and
  ``("qu", Quad)`` quads (Vermont uses all three but no ``m`` items).
* **Units bug** — ``PDFWallElement.length_inches`` used to be
  ``length_pts / 72.0``, correct only for 1:1 drawings. Real
  architectural PDFs are drawn at ``1/4"=1'-0"`` (48x reduction) or
  ``1/8"=1'-0"`` (96x). Post-Sprint-4f the parser detects scale from
  page-0 text (broadened regex for real-world variance), accepts a
  ``manual_scale`` override, and falls back to 1:1 with a warning.

The parser's public API stays compatible: ``PDFParser(file_path)`` still
works. New optional ``manual_scale`` argument turns scale awareness on.
"""

from __future__ import annotations

import fitz  # PyMuPDF
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# Minimum wall length in real-world inches. The tightest cutoff that
# still filters typical hatch fragments and annotation ticks (usually
# <0.5 in) while preserving legit short construction (jamb returns
# 3-6 in, wing walls 4-12 in, corner returns 4-8 in). Surfaced as a
# constant so future tuning is one-line.
MIN_WALL_LENGTH_IN = 1.0


# ---------------------------------------------------------------------------
# Scale parsing
# ---------------------------------------------------------------------------


# Broadened regex for real-world variance in scale annotations:
# * Optional "SCALE:" / "Scale " prefix (some title blocks show just the ratio)
# * Straight or curly quotes on the drawn measurement (" ″ “ ”)
# * ``=`` OR em-dash between drawn and real
# * Straight or curly apostrophe on the real-world feet (' ′ ’)
_QUOTE = r'["″“”]?'
_FT = r"['′’]?"
SCALE_PATTERN = re.compile(
    r'(?:SCALE[:\s]+)?'
    r'(\d+(?:/\d+)?(?:\.\d+)?)\s*'
    + _QUOTE
    + r'\s*[=—]\s*'
    + r'(\d+(?:\.\d+)?)\s*'
    + _FT,
    re.IGNORECASE,
)


class ScaleParseError(ValueError):
    """Raised by :func:`_parse_scale_string` for unparseable inputs."""


def _parse_fraction(s: str) -> float:
    """Parse ``"1/4"``, ``"0.25"``, or ``"3"`` into a float."""
    s = s.strip()
    if "/" in s:
        n, d = s.split("/", 1)
        return float(n) / float(d)
    return float(s)


def _parse_scale_string(s: str) -> float:
    """Convert a ``1/4"=1'-0"``-style scale into ``inches per PDF point``.

    1 PDF point = 1/72 PDF inch. At ``1/4"=1'`` scale, 0.25 PDF inches
    represent 12 real inches, so 1 PDF point represents
    ``12/(0.25*72) = 0.667`` real inches.

    Generalised: ``scale_in_per_pt = (real_ft * 12) / (drawn_in * 72)``.
    """
    m = re.match(
        r'(\d+(?:/\d+)?(?:\.\d+)?)\s*'
        + _QUOTE
        + r'\s*[=—]\s*'
        + r'(\d+(?:\.\d+)?)\s*'
        + _FT,
        s.strip(),
    )
    if not m:
        raise ScaleParseError(f"unparseable scale: {s!r}")
    drawn_in = _parse_fraction(m.group(1))
    real_ft = float(m.group(2))
    if drawn_in <= 0:
        raise ScaleParseError(f"non-positive drawn measurement in {s!r}")
    return (real_ft * 12.0) / (drawn_in * 72.0)


# ---------------------------------------------------------------------------
# Wall element
# ---------------------------------------------------------------------------


class PDFWallElement:
    """Represents a wall extracted from PDF.

    ``start_point`` / ``end_point`` remain in raw PDF points (1/72 inch).
    ``length_inches`` scales those points to real-world inches using the
    ``scale_in_per_pt`` supplied by the owning :class:`PDFParser`.
    """

    def __init__(
        self,
        start_point: Tuple[float, float],
        end_point: Tuple[float, float],
        page_number: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
        scale_in_per_pt: float = 1.0 / 72.0,
    ):
        self.start_point = start_point
        self.end_point = end_point
        self.page_number = page_number
        self.metadata = metadata or {}
        self._scale_in_per_pt = scale_in_per_pt

    @property
    def length(self) -> float:
        """Raw PDF-point distance between endpoints (unchanged by scale)."""
        dx = self.end_point[0] - self.start_point[0]
        dy = self.end_point[1] - self.start_point[1]
        return (dx ** 2 + dy ** 2) ** 0.5

    @property
    def length_inches(self) -> float:
        """Wall length in real-world inches at the parser's detected scale.

        At the 1:1 fallback (``scale_in_per_pt == 1/72``) this reduces to
        ``length / 72`` — matching the pre-Sprint-4f behaviour so existing
        callers on unscaled PDFs see the same numbers (with a populated
        ``scale_warning`` on the parser).
        """
        return self.length * self._scale_in_per_pt

    def __repr__(self):
        return (
            f"<PDFWall(length_in={self.length_inches:.2f}, "
            f"page={self.page_number})>"
        )


# ---------------------------------------------------------------------------
# PDF parser
# ---------------------------------------------------------------------------


class PDFParser:
    """Parser for PDF architectural drawings.

    Scale is detected once during :meth:`load` via a cascade:

    1. ``manual_scale`` argument (Sprint 4e-style string) — wins if
       parseable.
    2. Auto-detect from page-0 raw text via :data:`SCALE_PATTERN` —
       parses ``"SCALE: 1/4\\"=1'-0\\""`` and looser variants.
    3. Fallback to 1:1 (``scale_in_per_pt == 1/72``) with a populated
       ``scale_warning`` — matches the pre-Sprint-4f numerical
       behaviour so existing callers don't regress silently.
    """

    def __init__(self, file_path: str, manual_scale: Optional[str] = None):
        """Initialize PDF parser.

        Args:
            file_path: Path to PDF file.
            manual_scale: Optional scale override string, e.g.
                ``"1/4\\"=1'-0\\""``. Wins over auto-detect.
        """
        self.file_path = Path(file_path)
        self.doc: Optional[fitz.Document] = None
        self.walls: List[PDFWallElement] = []
        self.texts: List[Dict[str, Any]] = []
        self._manual_scale = manual_scale
        # Populated by _detect_scale during load().
        self.scale_in_per_pt: float = 1.0 / 72.0
        self.scale_source: str = "unknown"          # "manual" | "auto_text" | "unknown"
        self.scale_warning: Optional[str] = None

    def load(self) -> bool:
        """Load the PDF file and detect drawing scale.

        Returns True on success. On success, ``scale_*`` fields are
        populated per the detection cascade.
        """
        try:
            logger.info(f"Loading PDF file: {self.file_path}")
            self.doc = fitz.open(str(self.file_path))
        except Exception as e:
            logger.error(f"Failed to load PDF {self.file_path}: {e}")
            return False
        logger.info(f"Successfully loaded {self.file_path.name} ({len(self.doc)} pages)")
        self._detect_scale()
        return True

    def _detect_scale(self) -> None:
        """Populate ``scale_in_per_pt`` / ``scale_source`` / ``scale_warning``.

        Cascade: manual > auto_text > 1:1 fallback.
        """
        if self._manual_scale:
            try:
                self.scale_in_per_pt = _parse_scale_string(self._manual_scale)
                self.scale_source = "manual"
                return
            except ScaleParseError:
                logger.warning(
                    "manual_scale %r unparseable; trying auto-detect",
                    self._manual_scale,
                )
        if self.doc and len(self.doc):
            text = self.doc[0].get_text()
            m = SCALE_PATTERN.search(text)
            if m:
                candidate = f'{m.group(1)}"={m.group(2)}\''
                try:
                    self.scale_in_per_pt = _parse_scale_string(candidate)
                    self.scale_source = "auto_text"
                    return
                except ScaleParseError:  # pragma: no cover - SCALE_PATTERN matches iff _parse_scale_string can parse the same shape
                    pass
        self.scale_warning = (
            "Could not detect drawing scale; falling back to 1:1 PDF points. "
            "Wall lengths will be wrong for any drawing not at 1:1. "
            "Pass `manual_scale` (e.g., `1/4\"=1'-0\"`) to override."
        )

    def extract_walls(
        self, page_numbers: Optional[List[int]] = None
    ) -> List[PDFWallElement]:
        """Extract wall elements from the requested pages.

        Filters walls shorter than :data:`MIN_WALL_LENGTH_IN` real-world
        inches to strip annotation tick marks and hatch fragments.
        """
        if not self.doc:
            logger.error("No document loaded")
            return []

        self.walls = []

        if page_numbers is None:
            pages_to_process = range(len(self.doc))
        else:
            pages_to_process = page_numbers

        for page_num in pages_to_process:
            if page_num >= len(self.doc):
                logger.warning(f"Page {page_num} out of range, skipping")
                continue

            page = self.doc[page_num]
            page_walls = self._extract_walls_from_page(page, page_num)
            self.walls.extend(page_walls)

        logger.info(
            f"Extracted {len(self.walls)} wall elements from "
            f"{len(list(pages_to_process))} pages (scale_source={self.scale_source})"
        )
        return self.walls

    def _extract_walls_from_page(
        self, page: fitz.Page, page_num: int
    ) -> List[PDFWallElement]:
        walls: List[PDFWallElement] = []
        try:
            paths = page.get_drawings()
        except Exception as e:  # pragma: no cover - defensive against PyMuPDF crashes on malformed docs
            logger.warning(f"Error extracting drawings from page {page_num}: {e}")
            return walls

        for path in paths:
            items = path.get("items", [])
            if len(items) < 1:
                continue
            walls.extend(self._convert_path_to_walls(items, page_num))

        return [w for w in walls if w.length_inches >= MIN_WALL_LENGTH_IN]

    def _convert_path_to_walls(
        self, items: List[Tuple], page_num: int
    ) -> List[PDFWallElement]:
        """Walk one path's items and emit :class:`PDFWallElement` per segment.

        Handles the item shapes surfaced by the Sprint 4f Vermont spike:

        * ``("m", p)`` — move-to; sets ``current_point``.
        * ``("l", p)`` — line-to relative to ``current_point`` (older PyMuPDF).
        * ``("l", p1, p2)`` — explicit line (newer PyMuPDF; Vermont uses this).
        * ``("re", Rect)`` — rectangle unpacked into 4 walls.
        * ``("qu", Quad)`` — quadrilateral unpacked into 4 walls (Vermont).
        * ``("c", ...)`` — cubic bezier; skipped as wall but advances
          ``current_point`` to the last point in the tuple so subsequent
          ``("l", p)`` items still resolve.
        * anything else — skipped.
        """
        walls: List[PDFWallElement] = []
        current_point: Optional[Tuple[float, float]] = None

        for item in items:
            cmd = item[0]

            if cmd == "m":
                current_point = self._pt(item[1])

            elif cmd == "l":
                if len(item) >= 3:
                    # ("l", p1, p2): explicit line
                    start = self._pt(item[1])
                    end = self._pt(item[2])
                    walls.append(self._wall(start, end, page_num, source="line"))
                    current_point = end
                else:
                    # ("l", p): relative to current_point
                    if current_point is None:
                        continue
                    end = self._pt(item[1])
                    walls.append(
                        self._wall(current_point, end, page_num, source="line")
                    )
                    current_point = end

            elif cmd == "re":
                rect = item[1]
                corners = [
                    (rect.x0, rect.y0),
                    (rect.x1, rect.y0),
                    (rect.x1, rect.y1),
                    (rect.x0, rect.y1),
                ]
                walls.extend(self._perimeter_walls(corners, page_num, source="rect"))
                current_point = corners[-1]

            elif cmd == "qu":
                quad = item[1]
                # PyMuPDF Quad stores 4 corners as ul, ur, ll, lr.
                # Perimeter order matters — we want a closed loop.
                corners = [
                    self._pt(quad.ul),
                    self._pt(quad.ur),
                    self._pt(quad.lr),
                    self._pt(quad.ll),
                ]
                walls.extend(self._perimeter_walls(corners, page_num, source="quad"))
                current_point = corners[-1]

            elif cmd == "c":
                # Cubic bezier: skipped as a wall, but advance current_point to
                # the last point in the tuple so following ("l", p) items still
                # resolve against the curve endpoint.
                if len(item) >= 2:
                    current_point = self._pt(item[-1])
                # else: no points at all — defensive fall-through

            # Other item shapes (unknown commands) fall through silently.

        return walls

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _pt(p) -> Tuple[float, float]:
        """Normalize a PyMuPDF Point (or tuple) to a plain ``(x, y)`` tuple."""
        if hasattr(p, "x") and hasattr(p, "y"):
            return (float(p.x), float(p.y))
        return (float(p[0]), float(p[1]))

    def _wall(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        page_num: int,
        source: str,
    ) -> PDFWallElement:
        return PDFWallElement(
            start_point=start,
            end_point=end,
            page_number=page_num,
            metadata={"type": source},
            scale_in_per_pt=self.scale_in_per_pt,
        )

    def _perimeter_walls(
        self,
        corners: List[Tuple[float, float]],
        page_num: int,
        source: str,
    ) -> List[PDFWallElement]:
        """Emit 4 walls closing a rectangle/quad's perimeter."""
        return [
            self._wall(a, b, page_num, source=source)
            for a, b in zip(corners, corners[1:] + corners[:1])
        ]

    # ------------------------------------------------------------------
    # Unchanged accessors
    # ------------------------------------------------------------------

    def extract_text(
        self, page_numbers: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        """Extract text blocks (with positions) from the requested pages."""
        if not self.doc:
            logger.error("No document loaded")
            return []

        self.texts = []

        if page_numbers is None:
            pages_to_process = range(len(self.doc))
        else:
            pages_to_process = page_numbers

        for page_num in pages_to_process:
            if page_num >= len(self.doc):
                continue

            page = self.doc[page_num]
            text_blocks = page.get_text("dict")["blocks"]
            for block in text_blocks:
                if block.get("type") == 0:
                    for line in block.get("lines", []):
                        text = " ".join(
                            [span["text"] for span in line.get("spans", [])]
                        )
                        if text.strip():
                            self.texts.append(
                                {
                                    "text": text.strip(),
                                    "page": page_num,
                                    "bbox": line.get("bbox"),
                                }
                            )

        logger.info(f"Extracted {len(self.texts)} text blocks")
        return self.texts

    def get_drawing_info(self) -> Dict[str, Any]:
        """Get general information about the PDF."""
        if not self.doc:
            return {}
        return {
            "filename": self.file_path.name,
            "page_count": len(self.doc),
            "format": "PDF",
            "metadata": self.doc.metadata,
            "scale_source": self.scale_source,
            "scale_warning": self.scale_warning,
        }

    def close(self):
        """Close the PDF document."""
        if self.doc:
            self.doc.close()
            self.doc = None
