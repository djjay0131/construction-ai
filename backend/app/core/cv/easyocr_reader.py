"""EasyOCR-backed implementation of the Sprint 4a ``OcrReader`` Protocol.

Lazy initialisation: ``easyocr.Reader(...)`` downloads ~200 MB of model
weights on first instantiation. To keep import-time fast and unit tests
mockable, the underlying reader is created on the first ``readtext()``
call, not in ``__init__``. The ``easyocr`` module itself is also
imported lazily so test environments without easyocr installed don't
break at import time.

The native ``easyocr.Reader.readtext()`` returns
``[(quad_points, text, confidence), ...]`` where ``quad_points`` is a
4-point polygon describing a (possibly rotated) rectangle around the
text. This adapter collapses quads to axis-aligned bboxes via min/max —
``(x1, y1, x2, y2)`` — matching the ``TextBox`` shape that downstream
catalog code already knows.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence

from app.core.cv.dimension_extractor import TextBox

logger = logging.getLogger(__name__)


class EasyOcrReader:
    """OcrReader satisfying the Sprint 4a Protocol, backed by EasyOCR."""

    def __init__(
        self,
        languages: Sequence[str] | None = None,
        gpu: bool = False,
    ) -> None:
        self.languages = list(languages or ["en"])
        self.gpu = gpu
        self._reader: Any = None  # lazy

    def _get_reader(self) -> Any:
        """Return the underlying ``easyocr.Reader``, constructing it on first use."""
        if self._reader is None:
            # Lazy import so test environments without easyocr installed
            # don't fail at module import time.
            import easyocr  # type: ignore[import]

            logger.info(
                "Initialising EasyOCR Reader (languages=%s, gpu=%s) — "
                "first use will download ~200 MB of model weights.",
                self.languages,
                self.gpu,
            )
            self._reader = easyocr.Reader(self.languages, gpu=self.gpu)
        return self._reader

    def readtext(self, image: Any) -> list[TextBox]:
        """Run OCR and return axis-aligned ``TextBox`` list."""
        reader = self._get_reader()
        raw = reader.readtext(image)
        return [self._to_textbox(entry) for entry in raw]

    @staticmethod
    def _to_textbox(entry: tuple) -> TextBox:
        """Translate one ``(quad_points, text, confidence)`` entry to a TextBox."""
        quad, text, confidence = entry
        xs = [int(p[0]) for p in quad]
        ys = [int(p[1]) for p in quad]
        bbox = (min(xs), min(ys), max(xs), max(ys))
        return TextBox(text=str(text), bbox=bbox, confidence=float(confidence))
