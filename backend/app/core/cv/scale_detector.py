"""Scale detection cascade for raster construction drawings.

Three tiers, first-success-wins:

1. **Reference measurement** — caller supplies a known wall index + its
   real length in inches. Scale = pixel_length / inches.
2. **Manual scale string** — caller supplies the drawing's documented
   scale (e.g. ``"1/4\\"=1'-0\\""``). Parser uses a 96-DPI paper
   assumption.
3. **Auto-detect** — Gemini Vision title-block read + OCR scale bar.
   **NOT implemented in Sprint 3b.** Always raises :class:`ScaleWarning`
   with instructions to provide a manual override or reference.

Every successful candidate is then run through a plausibility check —
every wall must fall in ``[2', 80']``. Failure raises :class:`ScaleWarning`.
"""

from __future__ import annotations

import logging
import math
import re
from typing import Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)

PixelPoint = Tuple[int, int]
PixelSegment = Tuple[PixelPoint, PixelPoint]

# Paper DPI assumption used by parse_manual_scale.
PAPER_DPI = 96.0
# Plausibility bounds for residential walls.
DEFAULT_MIN_WALL_IN = 24.0   # 2 ft
DEFAULT_MAX_WALL_IN = 960.0  # 80 ft

_MANUAL_SCALE_RE = re.compile(
    r"""^\s*
        (?P<num>\d+)
        \s*/\s*
        (?P<den>\d+)
        \s*"\s*=\s*
        (?P<ft>\d+)'
        (?:\s*-\s*(?P<in>\d+)\"?)?
        \s*$""",
    re.VERBOSE,
)
_MANUAL_SCALE_WHOLE_RE = re.compile(
    r"""^\s*
        (?P<paper_in>\d+)"\s*=\s*
        (?P<ft>\d+)'
        (?:\s*-\s*(?P<in>\d+)\"?)?
        \s*$""",
    re.VERBOSE,
)


class ScaleWarning(RuntimeError):
    """Raised when no tier of the cascade produces a plausible scale.

    The message always tells the caller how to proceed (manual_scale or
    reference_measurement).
    """


def parse_manual_scale(text: str) -> float:
    """Parse a scale string into pixels-per-inch (assuming 96 DPI paper).

    Accepts: ``1/4"=1'-0"``, ``1/8"=1'``, ``1"=1'-0"``, etc.
    Returns scale_px_per_in. Raises :class:`ScaleWarning` on parse failure.
    """
    if not isinstance(text, str) or not text.strip():
        raise ScaleWarning(f"manual_scale is empty; got {text!r}")

    m = _MANUAL_SCALE_RE.match(text)
    if m:
        den = float(m["den"])
        if den == 0:
            raise ScaleWarning(
                f"manual_scale {text!r} has zero denominator on the paper side"
            )
        paper_in = float(m["num"]) / den
    else:
        m = _MANUAL_SCALE_WHOLE_RE.match(text)
        if not m:
            raise ScaleWarning(
                f"manual_scale {text!r} not in a recognised format "
                "(expected like '1/4\"=1'-0\"' or '1\"=1'-0\")"
            )
        paper_in = float(m["paper_in"])

    feet = float(m["ft"])
    inches = float(m["in"] or 0)
    real_in = feet * 12.0 + inches
    if paper_in <= 0 or real_in <= 0:
        raise ScaleWarning(
            f"manual_scale {text!r} parsed to non-positive paper/real measurement"
        )

    # 1 paper inch at 96 DPI = 96 pixels. paper_in is in paper-inches.
    paper_px = paper_in * PAPER_DPI
    return paper_px / real_in


def _segment_length_px(seg: PixelSegment) -> float:
    (x1, y1), (x2, y2) = seg
    return math.hypot(x2 - x1, y2 - y1)


class ScaleDetector:
    """3-tier scale-detection cascade with plausibility check."""

    def __init__(
        self,
        min_wall_in: float = DEFAULT_MIN_WALL_IN,
        max_wall_in: float = DEFAULT_MAX_WALL_IN,
    ) -> None:
        if min_wall_in <= 0:
            raise ValueError(f"min_wall_in must be positive; got {min_wall_in}")
        if max_wall_in <= min_wall_in:
            raise ValueError(
                f"max_wall_in must exceed min_wall_in; got {max_wall_in} <= {min_wall_in}"
            )
        self.min_wall_in = min_wall_in
        self.max_wall_in = max_wall_in

    def detect(
        self,
        image: np.ndarray,
        segments_px: Sequence[PixelSegment],
        manual_scale: Optional[str] = None,
        reference: Optional[dict] = None,
    ) -> float:
        """Return pixels-per-inch. Raises :class:`ScaleWarning` if all tiers fail."""
        scale: Optional[float] = None

        if reference is not None:
            scale = self._scale_from_reference(segments_px, reference)
        elif manual_scale is not None:
            scale = parse_manual_scale(manual_scale)
        else:
            raise ScaleWarning(
                "Could not auto-detect scale. Provide either a manual_scale "
                'string (e.g. "1/4\\"=1\'-0\\"") or a reference_measurement '
                '({"wall_index": N, "length_inches": L}).'
            )

        self._check_plausible(scale, segments_px)
        return scale

    def _scale_from_reference(
        self,
        segments_px: Sequence[PixelSegment],
        reference: dict,
    ) -> float:
        try:
            idx = int(reference["wall_index"])
            length_in = float(reference["length_inches"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ScaleWarning(
                f"reference must have integer 'wall_index' and numeric "
                f"'length_inches'; got {reference!r}"
            ) from exc
        if length_in <= 0:
            raise ScaleWarning(
                f"reference length_inches must be positive; got {length_in}"
            )
        if idx < 0 or idx >= len(segments_px):
            raise ScaleWarning(
                f"reference wall_index {idx} out of range "
                f"(have {len(segments_px)} segments)"
            )
        px = _segment_length_px(segments_px[idx])
        if px <= 0:
            raise ScaleWarning(
                f"reference wall_index {idx} has zero pixel length"
            )
        return px / length_in

    def _check_plausible(
        self,
        scale_px_per_in: float,
        segments_px: Sequence[PixelSegment],
    ) -> None:
        for i, seg in enumerate(segments_px):
            px = _segment_length_px(seg)
            inches = px / scale_px_per_in
            if inches < self.min_wall_in or inches > self.max_wall_in:
                raise ScaleWarning(
                    f"Plausibility check failed: segment {i} would render "
                    f"as {inches:.1f} in, outside [{self.min_wall_in:.0f}, "
                    f"{self.max_wall_in:.0f}] in. Provide a reference_measurement "
                    "or check the manual_scale string."
                )
