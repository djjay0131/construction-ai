# Sprint 4a: OCR Dimension Parser + Extractor

**Status:** IMPLEMENTED
**Date:** 2026-06-14
**Implemented:** 2026-06-14
**Author:** Jason Cusati (with AI assistance)
**Sprint:** 4a of 2 (Sprint 4 — OCR Dimension Extraction & Object Catalog)
**Supersedes:** the "pure parsing + OCR extraction" slice of
`llm/features/ocr-dimension-extraction.md` (SPECIFIED 2026-04-01).
4b will add ObjectCatalogBuilder, CatalogStore, takeoff pipeline
integration, the `/api/catalog` endpoint, and the 7 catalog-dependent ACs.

## Problem

The parent Sprint 4 spec (459 lines, 10 ACs) is too big for one
constellize cycle to ship verifiably. Sprint 4a takes the cleanest-contract
pieces — a pure regex dimension parser and a bbox-preserving OCR extractor
that uses an injected reader (Protocol) — so the rest of Sprint 4 has a
solid foundation to build on.

## Goals

- `DimensionParser` translates architectural dimension strings into
  inches as `float`, handling the four common formats:
  imperial (`12'-6"`), inches-only (`36"`), fractional
  (`12'-6 1/2"`), and metric (`3600mm`, `3.6m`).
- `DimensionExtractor` runs the OCR reader over an image and returns
  structured `(text, bbox, parsed_inches)` triples — only entries the
  parser successfully recognises survive. Untouched OCR text is also
  surfaced (`raw_texts`) for downstream room-name detection in 4b.
- The OCR reader is **Protocol-typed** so tests pass in a fake instead
  of loading real EasyOCR (~200 MB model download, ~10 s init).
- ≥80% line coverage. Zero regression in Sprint 2 + 3 tests.

## Non-Goals

- `ObjectCatalogBuilder` (NetworkX graph) — 4b.
- `CatalogStore` (JSON/GraphML serialization) — 4b.
- Takeoff-pipeline integration — 4b.
- `/api/catalog` endpoint — 4b.
- Spatial association of dimensions with walls — 4b.
- Validation of OCR-against-geometry — 4b.
- Real EasyOCR integration in the takeoff path — 4b wires
  `FloorPlanAnalysisService`'s reader through.

## Design Approach

### `DimensionParser` (`backend/app/core/cv/dimension_parser.py`)

Pure function plus a tiny class wrapper. Patterns match the parent
spec's Section "Sample Implementation" (dimension regexes there are
the contract; this module IS the implementation of that contract).

```python
class DimensionParseError(ValueError):
    """Raised when a string doesn't match any known dimension format."""

def parse_dimension(text: str) -> float:
    """Return the dimension in inches.

    Recognised formats (case-insensitive whitespace tolerated):
    * Imperial whole-foot:     "12'", "12 ft"
    * Imperial ft + in:        "12'-6\"", "12'-6", "12 ft 6 in"
    * Imperial fractional:     "12'-6 1/2\"", "6 1/2\""
    * Inches only:             "36\"", "36 in"
    * Metric mm:               "3600mm", "3600 mm"
    * Metric m:                "3.6m", "3.6 m"

    Raises DimensionParseError on no-match.
    """

class DimensionParser:
    """Convenience wrapper exposing a stable interface plus a
    `parse_many` that tolerates failures (returns the survivors)."""
```

`parse_many` returns `list[tuple[str, float]]` — only entries that
parsed. This is the "graceful degradation" path (AC-9 from parent).

### `DimensionExtractor` (`backend/app/core/cv/dimension_extractor.py`)

```python
@dataclass(frozen=True)
class TextBox:
    text: str
    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2)
    confidence: float

@dataclass(frozen=True)
class ParsedDimension:
    text: str
    bbox: tuple[int, int, int, int]
    inches: float
    confidence: float

class OcrReader(Protocol):
    """Minimal contract: read text with bounding boxes from an image.
    Real implementations wrap EasyOCR's readtext().
    """
    def readtext(self, image) -> list[TextBox]: ...

class DimensionExtractor:
    def __init__(self, reader: OcrReader, parser: DimensionParser | None = None): ...

    def extract(self, image) -> tuple[list[ParsedDimension], list[TextBox]]:
        """Return (parsed_dimensions, raw_texts). raw_texts includes
        EVERY OCR detection so downstream code can do room-name
        association etc. parsed_dimensions only includes entries the
        parser recognised."""
```

### Why a Protocol instead of importing easyocr

EasyOCR initialisation downloads ~200 MB of models on first use and
takes ~10 s — turning every test in this module into a slow integration
test. The Protocol lets tests pass a 3-line `FakeReader` instead. The
real `FloorPlanAnalysisService` already wraps EasyOCR in Sprint 4b's
scope; this 4a feature only requires the contract.

## Sample Implementation

```python
# === backend/app/core/cv/dimension_parser.py ===
import re
from typing import Iterable

class DimensionParseError(ValueError): ...

_IMPERIAL_FT_IN = re.compile(
    r"^\s*(?P<ft>\d+)\s*'\s*(?:[-\s]\s*"
    r"(?P<in>\d+)(?:\s+(?P<num>\d+)\s*/\s*(?P<den>\d+))?\s*\"?)?\s*$"
)
_IMPERIAL_FT_WORDS = re.compile(
    r"^\s*(?P<ft>\d+)\s*ft(?:\s+(?P<in>\d+)\s*in)?\s*$",
    re.IGNORECASE,
)
_INCHES_ONLY = re.compile(
    r"^\s*(?P<int>\d+)(?:\s+(?P<num>\d+)\s*/\s*(?P<den>\d+))?\s*(?:\"|in)\s*$",
    re.IGNORECASE,
)
_METRIC_MM = re.compile(r"^\s*(?P<n>\d+(?:\.\d+)?)\s*mm\s*$", re.IGNORECASE)
_METRIC_M  = re.compile(r"^\s*(?P<n>\d+(?:\.\d+)?)\s*m\s*$",  re.IGNORECASE)

def parse_dimension(text: str) -> float:
    if not isinstance(text, str) or not text.strip():
        raise DimensionParseError(f"empty dimension; got {text!r}")
    # Imperial ft + in (covers "12'", "12'-6\"", "12'-6 1/2\"")
    m = _IMPERIAL_FT_IN.match(text)
    if m:
        ft = int(m["ft"])
        inches = int(m["in"] or 0)
        if m["num"]:
            inches += int(m["num"]) / int(m["den"])
        return float(ft * 12 + inches)
    # "12 ft 6 in"
    m = _IMPERIAL_FT_WORDS.match(text)
    if m:
        return float(int(m["ft"]) * 12 + int(m["in"] or 0))
    # Inches only
    m = _INCHES_ONLY.match(text)
    if m:
        inches = int(m["int"])
        if m["num"]:
            inches += int(m["num"]) / int(m["den"])
        return float(inches)
    # Metric
    m = _METRIC_MM.match(text)
    if m:
        return float(m["n"]) / 25.4
    m = _METRIC_M.match(text)
    if m:
        return float(m["n"]) / 0.0254
    raise DimensionParseError(f"unrecognised dimension format: {text!r}")
```

## Edge Cases & Error Handling

### Empty / None / whitespace
- **Scenario:** `parse_dimension("")`, `parse_dimension(None)`, `parse_dimension("   ")`
- **Behavior:** Raise `DimensionParseError` with the offending value in the message.
- **Test:** All three.

### Zero-foot edge cases
- **Scenario:** `parse_dimension("0'")`
- **Behavior:** Return `0.0`. (Zero-foot is technically valid; not our problem
  if the OCR misread.)
- **Test:** Explicit.

### Fractional-only ("6 1/2\"")
- **Scenario:** `parse_dimension("6 1/2\"")`
- **Behavior:** Return `6.5`.
- **Test:** Explicit.

### Zero denominator in a fraction
- **Scenario:** `parse_dimension("6 1/0\"")`
- **Behavior:** Raise `DimensionParseError` (zero-div would otherwise crash).
- **Test:** Explicit — the regex won't even match `1/0` properly; outcome
  documented.

### Garbage strings
- **Scenario:** `"random text"`, `"---"`, `"twelve feet"`
- **Behavior:** Raise `DimensionParseError`.
- **Test:** Parametrised.

### Metric mm vs m disambiguation
- **Scenario:** `"3.6m"` should be 3.6 metres; `"3600mm"` should be 3600 mm.
  Both round-trip to ~141.7 inches.
- **Behavior:** Distinct regexes; `m` is matched only when there's no `m`
  prefix.
- **Test:** Both, and verify they agree to <0.01 inches.

### `parse_many` survives partial failures
- **Scenario:** Input list has 3 parseable + 2 garbage entries.
- **Behavior:** Returns the 3 parseable entries.
- **Test:** Explicit.

### `DimensionExtractor` with empty OCR result
- **Scenario:** Reader returns `[]`.
- **Behavior:** Return `([], [])`.
- **Test:** Explicit.

### `DimensionExtractor` with OCR full of garbage
- **Scenario:** Reader returns 5 entries, none parseable as dimensions.
- **Behavior:** `parsed_dimensions=[]`, `raw_texts` has all 5 entries.
- **Test:** Explicit.

### `DimensionExtractor` happy path
- **Scenario:** Reader returns mix of dimensions + room names.
- **Behavior:** `parsed_dimensions` has only the dimensions; `raw_texts`
  has everything.
- **Test:** Explicit.

## Acceptance Criteria

### AC-1: Imperial ft-in formats parse
- **Given** strings: `"12'-6\""`, `"12'"`, `"36\""`, `"24'-0\""`
- **When** `parse_dimension(text)` is called
- **Then** the return values are `150.0`, `144.0`, `36.0`, `288.0`

### AC-2: Imperial fractional inches
- **Given** `"12'-6 1/2\""` and `"6 1/2\""`
- **When** parsed
- **Then** results are `150.5` and `6.5`

### AC-3: Metric formats
- **Given** `"3600mm"`, `"3.6m"`, `"914mm"`
- **When** parsed
- **Then** results are within 0.1 inches of `141.732…`, `141.732…`, `35.984`

### AC-4: Ft-word form
- **Given** `"12 ft 6 in"`, `"24 ft"`
- **When** parsed
- **Then** results are `150.0` and `288.0`

### AC-5: Empty / whitespace / None raise
- **Given** `""`, `"   "`, `None`
- **When** parsed
- **Then** `DimensionParseError` is raised with the offending value in
  the message

### AC-6: Garbage strings raise
- **Given** `"random"`, `"---"`, `"twelve feet"`
- **When** parsed
- **Then** `DimensionParseError` is raised

### AC-7: `parse_many` survives partial failures
- **Given** a list `["12'-6\"", "garbage", "24'"]`
- **When** `DimensionParser().parse_many(list)` is called
- **Then** the return is `[("12'-6\"", 150.0), ("24'", 288.0)]`

### AC-8: `DimensionExtractor` with empty OCR returns empties
- **Given** a fake reader returning `[]`
- **When** `extract(image)` is called
- **Then** the return is `([], [])`

### AC-9: `DimensionExtractor` separates parseable from raw
- **Given** a fake reader returning 4 text boxes: 2 dimensions, 1 room
  name, 1 garbage
- **When** `extract(image)` is called
- **Then** `parsed_dimensions` has 2 entries with their bboxes preserved,
  `raw_texts` has all 4

### AC-10: ≥80% line coverage + Sprint 3 regression
- **Given** the implementation is complete
- **When** `pytest tests/test_dimension_parser.py
  tests/test_dimension_extractor.py
  --cov=app.core.cv.dimension_parser
  --cov=app.core.cv.dimension_extractor` is run
- **Then** line coverage is ≥80% on each module
- **And** the 121 Sprint 2 + 3 tests still pass

## Technical Notes

- **Affected files:**
  - `backend/app/core/cv/dimension_parser.py` (new)
  - `backend/app/core/cv/dimension_extractor.py` (new)
  - `backend/tests/test_dimension_parser.py` (new)
  - `backend/tests/test_dimension_extractor.py` (new)
  - `.github/workflows/ci.yml` (add the two new test files + cov targets)
- **No new runtime dependencies.** `easyocr` is already pinned; real
  reader integration happens in 4b.
- **Test strategy:** the OCR reader is a Protocol; tests pass a
  `FakeReader` returning predetermined `TextBox` lists. No model
  download, no slow tests.

## Dependencies

- Sprint 3 VERIFIED (the parent spec's ImagePreprocessor + skew rejection
  cover AC-10 of the parent Sprint 4 spec).

## Open Questions

- Should the parser accept ranges like `"10'-12'"`? **Decision:** no in
  4a — ranges are rare in architectural dimensioning and adding them
  would balloon the regex. Defer.
- Should the parser auto-correct common OCR confusions
  (`l` → `1`, `O` → `0`)? **Decision:** no in 4a — the parser is
  syntactic; OCR correction belongs in the reader layer.
