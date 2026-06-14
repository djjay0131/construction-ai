"""OCR dimension extraction with bbox preservation.

Wraps an injected ``OcrReader`` (Protocol) so this module can be tested
without loading EasyOCR (~200 MB model download). The real reader gets
wired in Sprint 4b when the takeoff pipeline calls into the extractor.

The output is two lists:

* ``parsed_dimensions`` — only the OCR text boxes whose text parses as a
  dimension. Each entry preserves the original bbox so downstream
  spatial association (Sprint 4b) can place dimensions on walls.
* ``raw_texts`` — every OCR detection, parseable-or-not. Sprint 4b needs
  these for room-name labels.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

from app.core.cv.dimension_parser import (
    DimensionParseError,
    DimensionParser,
)

logger = logging.getLogger(__name__)

BBox = tuple[int, int, int, int]  # (x1, y1, x2, y2)


@dataclass(frozen=True)
class TextBox:
    """One OCR detection: text + axis-aligned bbox + reader confidence."""

    text: str
    bbox: BBox
    confidence: float


@dataclass(frozen=True)
class ParsedDimension:
    """A TextBox whose text was successfully parsed as a dimension."""

    text: str
    bbox: BBox
    inches: float
    confidence: float


class OcrReader(Protocol):
    """Minimal contract: ``readtext(image)`` returns a list of TextBox.

    Real implementations wrap EasyOCR's ``Reader.readtext()`` and
    translate its quad-point output into axis-aligned bboxes.
    """

    def readtext(self, image: Any) -> list[TextBox]: ...  # pragma: no cover


class DimensionExtractor:
    """Run an :class:`OcrReader` and split its output into parseable
    dimensions + raw text."""

    def __init__(
        self,
        reader: OcrReader,
        parser: DimensionParser | None = None,
    ) -> None:
        self.reader = reader
        self.parser = parser or DimensionParser()

    def extract(self, image: Any) -> tuple[list[ParsedDimension], list[TextBox]]:
        """Return ``(parsed_dimensions, raw_texts)``.

        ``raw_texts`` includes everything the reader returned (for
        downstream room-name detection in Sprint 4b). ``parsed_dimensions``
        is only entries whose text parsed; bbox + confidence are preserved.
        """
        raw_texts = list(self.reader.readtext(image))
        parsed: list[ParsedDimension] = []
        for tb in raw_texts:
            try:
                inches = self.parser.parse(tb.text)
            except DimensionParseError:
                continue
            parsed.append(
                ParsedDimension(
                    text=tb.text,
                    bbox=tb.bbox,
                    inches=inches,
                    confidence=tb.confidence,
                )
            )
        return parsed, raw_texts
