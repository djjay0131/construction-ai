"""Pure-regex architectural dimension parser.

Translates strings like ``"12'-6\\""`` into a single ``float`` of inches.
Recognised formats (case-insensitive; whitespace tolerated):

* Imperial whole-foot:     ``"12'"``, ``"12 ft"``
* Imperial ft + in:        ``"12'-6\\""``, ``"12'-6"``, ``"12 ft 6 in"``
* Imperial fractional:     ``"12'-6 1/2\\""``, ``"6 1/2\\""``
* Inches only:             ``"36\\""``, ``"36 in"``
* Metric mm:               ``"3600mm"``, ``"3600 mm"``
* Metric m:                ``"3.6m"``, ``"3.6 m"``

No I/O, no class state — just a function and a thin convenience wrapper
that survives partial failures in ``parse_many``. The OCR-reading layer
(`DimensionExtractor`) consumes this module.
"""

from __future__ import annotations

import re
from typing import Iterable

MM_PER_IN = 25.4
IN_PER_M = 1.0 / 0.0254


class DimensionParseError(ValueError):
    """Raised when a string doesn't match any known dimension format."""


# Imperial: "12'", "12'-6", "12'-6\"", "12'-6 1/2", "12'-6 1/2\""
_IMPERIAL_FT_IN = re.compile(
    r"""^\s*
        (?P<ft>\d+)
        \s*'\s*
        (?:
            [-\s]
            \s*
            (?P<inches>\d+)
            (?:\s+(?P<num>\d+)\s*/\s*(?P<den>\d+))?
            \s*"?
        )?
        \s*$""",
    re.VERBOSE,
)

# Word-form imperial: "12 ft", "12 ft 6 in"
_IMPERIAL_WORDS = re.compile(
    r"""^\s*
        (?P<ft>\d+)
        \s*ft
        (?:\s+(?P<inches>\d+)\s*in)?
        \s*$""",
    re.IGNORECASE | re.VERBOSE,
)

# Inches only: "36\"", "36 in", "6 1/2\""
_INCHES_ONLY = re.compile(
    r"""^\s*
        (?P<inches>\d+)
        (?:\s+(?P<num>\d+)\s*/\s*(?P<den>\d+))?
        \s*(?:"|in)\s*$""",
    re.IGNORECASE | re.VERBOSE,
)

# Metric millimetres
_METRIC_MM = re.compile(
    r"^\s*(?P<n>\d+(?:\.\d+)?)\s*mm\s*$",
    re.IGNORECASE,
)

# Metric metres (no 'm' immediately preceded by another 'm' — see _METRIC_MM)
_METRIC_M = re.compile(
    r"^\s*(?P<n>\d+(?:\.\d+)?)\s*m\s*$",
    re.IGNORECASE,
)


def _add_fraction(numerator: str | None, denominator: str | None) -> float:
    """Return numerator/denominator as a float, or 0.0 if either is missing."""
    if not numerator or not denominator:
        return 0.0
    den = int(denominator)
    if den == 0:
        raise DimensionParseError(
            f"zero denominator in fractional dimension: {numerator}/{denominator}"
        )
    return int(numerator) / den


def parse_dimension(text: str) -> float:
    """Parse one dimension string into a float of inches.

    Raises :class:`DimensionParseError` on no-match or invalid fraction.
    """
    if not isinstance(text, str) or not text.strip():
        raise DimensionParseError(f"empty dimension; got {text!r}")

    m = _IMPERIAL_FT_IN.match(text)
    if m:
        ft = int(m["ft"])
        inches = int(m["inches"] or 0)
        inches += _add_fraction(m["num"], m["den"])
        return float(ft * 12 + inches)

    m = _IMPERIAL_WORDS.match(text)
    if m:
        ft = int(m["ft"])
        inches = int(m["inches"] or 0)
        return float(ft * 12 + inches)

    m = _INCHES_ONLY.match(text)
    if m:
        inches = float(m["inches"])
        inches += _add_fraction(m["num"], m["den"])
        return inches

    m = _METRIC_MM.match(text)
    if m:
        return float(m["n"]) / MM_PER_IN

    m = _METRIC_M.match(text)
    if m:
        return float(m["n"]) * IN_PER_M

    raise DimensionParseError(f"unrecognised dimension format: {text!r}")


class DimensionParser:
    """Stable-named wrapper around :func:`parse_dimension` plus a
    failure-tolerant batch method.

    The extractor (:class:`DimensionExtractor`) holds one of these so
    callers can inject a custom parser in the future (e.g., to add
    OCR-confusion correction) without changing call sites.
    """

    def parse(self, text: str) -> float:
        return parse_dimension(text)

    def parse_many(self, texts: Iterable[str]) -> list[tuple[str, float]]:
        """Parse a batch and return only the successes.

        This is the "graceful degradation" path from the parent Sprint 4
        spec — when OCR returns 50 text boxes and 30 happen to be
        dimensions, the other 20 don't tank the whole pipeline.
        """
        out: list[tuple[str, float]] = []
        for text in texts:
            try:
                out.append((text, parse_dimension(text)))
            except DimensionParseError:
                continue
        return out
