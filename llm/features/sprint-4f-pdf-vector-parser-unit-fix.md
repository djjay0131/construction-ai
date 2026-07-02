# Sprint 4f: PDF Vector-Parser Unit + Path-Walking Fix

**Status:** IMPLEMENTED
**Date:** 2026-06-25
**Implemented:** 2026-07-02
**Author:** Jason Cusati (with AI assistance)
**Sprint:** 4f of 5 (interstitial — bug-fix sprint surfaced by Sprint 5)
**Depends on:** Sprint 4e VERIFIED.

## Problem

The vector PDF code path produces wrong (and often zero) walls on
real-world floor plans, surfaced concretely by Sprint 5's
Vermont-Microhouse fixture:

> Vermont's 8.6×24 PDF: 2022 vector drawings parsed → **0 walls
> extracted**.

Two stacked bugs:

1. **Path-walking bug.** `PDFParser._convert_path_to_walls` assumes
   PyMuPDF emits `("m", p)` (move-to) immediately followed by
   `("l", p)` (line-to) — the older PyMuPDF API. Real-world PDFs
   emit either form depending on PyMuPDF version + the producing
   tool: explicit `("l", p1, p2)` lines, `("re", rect)` rectangles
   (which the parser references but never unpacks into walls), or
   the older move-then-line pair. The current logic only handles
   the last case, so most real PDFs yield 0 walls.
2. **Units bug.** `PDFWallElement.length_inches` returns
   `length_pts / 72.0`, which is correct ONLY when the drawing is
   at 1:1 scale. For the typical architectural `1/4"=1'-0"` scale,
   the returned length is off by 48× — a 16 ft wall reports as
   4 inches.

Sprint 5 caught both via the Vermont fixture, which was deferred as
a result. Without this fix, Vermont stays deferred and no real-world
vector PDF gets a correct takeoff.

## Goals

- **Path walking handles both PyMuPDF item formats** —
  `("m", p1); ("l", p2)` (old) AND `("l", p1, p2)` (new) — plus
  `("re", rect)` rectangles unpacked into 4 walls.
- **Scale-aware unit conversion**:
  - `PDFParser.__init__(manual_scale=None)` accepts a Sprint 4e-
    style scale string (`"1/4\"=1'-0\""`).
  - `PDFParser.load()` runs `_detect_scale()`: tries manual override
    first, then auto-detects from page-0 text via
    `page.get_text()` + a `SCALE:` regex, then falls back to 1:1 +
    a populated `scale_warning`.
  - `PDFParser.scale_in_per_pt`, `scale_source` ∈ {`manual`,
    `auto_text`, `unknown`}, and `scale_warning: Optional[str]`
    are first-class observable fields.
- **`PDFWallElement.length_inches` honors the parser's scale** —
  `(pdf_distance_pt) * scale_in_per_pt` yields real-world inches.
- **`run_pdf_takeoff` threads `manual_scale` into PDFParser** — the
  param already flows through to the raster fallback; Sprint 4f
  also makes it reach the vector branch.
- **Length filter retuned** — drop the `> 5 PDF points` raw filter.
  Replace with `≥ 1.0 real-world inch`. The tightest cutoff that
  still filters sub-tick-mark artifacts (hatch fragments,
  annotation ticks are typically <0.5 in) without eating legitimate
  short construction segments (jamb returns 3-6 in, wing walls
  4-12 in, corner returns 4-8 in). Threshold surfaced as a named
  constant `MIN_WALL_LENGTH_IN` for future tuning.
- **Backward-compatible default**: `PDFParser(file_path)` with no
  `manual_scale` and no auto-detectable annotation → falls back to
  1:1 with `scale_warning` populated. Existing callers see the
  same numerical behavior as today (the bug), but now with
  observable provenance.
- **Vermont fixture turns active**: once the path-walking fix lands,
  Vermont produces walls > 0 (smoke-only — its scale is unlikely to
  auto-detect from text; LF accuracy isn't gated).
- ≥80% line coverage on the modified `pdf_parser.py`; zero
  regression in the prior 293 Sprint 2/3/4/5 tests.

## Non-Goals

- **Curve / Bezier extraction** — `("c", ...)` cubic-bezier path
  items remain skipped (skip behavior already documented; not a
  Sprint 4f regression).
- **Multi-page scale detection** — Sprint 4f auto-detects from
  page 0 only. Multi-page plans with per-page scales are rare in
  the residential domain; Sprint 4e's per-page dispatch model
  means each scanned page already gets independent scale
  detection via the raster pipeline.
- **Scale-bar geometry inspection** — auto-detection from graphical
  scale bars (the "0─5─10 ft" pictograph at the bottom of a sheet)
  is out of scope. Text annotations are the practical surface.
- **OCR'd scale from a rasterized page** — Sprint 4f auto-detects
  only via PyMuPDF's vector text extraction. If the scale is
  itself a raster image (handwritten / scanned title block on a
  vector PDF), it won't be picked up. That's what the manual
  override is for.
- **Header sizing / structural inference from PDF metadata** —
  scope-creep into Phase 2 territory.
- **Vermont as a gated fixture** — `references.json` updates to
  flip Vermont's role from skipped to smoke-only happen here, but
  hand-counting a reference for it is not a Sprint 4f task.

## User Stories

- **As a takeoff operator**, I want to upload a CAD-exported PDF at
  any standard architectural scale (1/4"=1'-0", 1/8"=1'-0",
  3/16"=1'-0", etc.) and get a takeoff with correct linear-foot
  measurements, so that my BOM matches my plan.
- **As a takeoff operator who uploaded a PDF without a parseable
  scale annotation**, I want a clear warning surfaced (in the
  takeoff response and the API logs) so that I know to re-upload
  with a manual scale override.
- **As Sprint 5's e2e harness**, I want Vermont to actually produce
  walls so that the vector-PDF dispatch path is exercised
  end-to-end.

## Design Approach

### Phase 0 (before drafting tests): Vermont shape spike

**Rationale**: the current parser produced 0 walls from Vermont's
2022 vector paths, which means either (a) Vermont uses item shapes
outside the documented `m` / `l` / `re` set, (b) the current
walking logic has a bug we haven't identified, or (c) both.
Committing tests to specific shapes before checking risks writing
tests against the wrong assumptions.

Before writing any test code, run a quick characterization script:

```python
# One-shot investigation; not committed
import fitz, collections
doc = fitz.open("backend/tests/fixtures/phase1/vector_pdf_vermont.pdf")
counter = collections.Counter()
for path in doc[0].get_drawings():
    for item in path.get("items", []):
        counter[(item[0], len(item))] += 1
print(counter.most_common())
```

Output pins down what item shapes are actually present. If Vermont
uses only `m` / `l` / `re`, the handling table above is complete
and AC-15 applies. If Vermont uses additional shapes (`c` curves
we treat as advance-only, filled paths, sub-paths, etc.), the
handling table extends before AC-14 tests get written.

The spike takes ~5 minutes and prevents committing to behavior we
haven't observed.

### Scale unit math

```
1 PDF point = 1/72 PDF inch
Scale "1/4\"=1'-0\"": 0.25 PDF inches represent 12 real inches.
  → 1 PDF inch represents 48 real inches.
  → 1 PDF point represents (1/72 PDF inch) × 48 = 0.667 real inches.
  → scale_in_per_pt = 12 / (0.25 × 72) = 0.667

Generalization: scale_in_per_pt = (real_ft × 12) / (drawn_in × 72)
```

`PDFWallElement.length_inches` = `pdf_distance_pt * scale_in_per_pt`.

### Scale-pattern regex (broadened for real-world variance)

Real PDFs use many scale-annotation formats. The regex must handle:

* Optional "SCALE" prefix — some title blocks just show the ratio
* Case variants — "SCALE:", "Scale:", "scale:"
* Whitespace variants
* Straight quotes AND curly (typographic) quotes — `1/4"` vs `1/4″`
* Both `=` and em-dash `—` separators — `1/4"=1'` vs `1/4"—1'`

```python
# Straight-quote + curly-quote character classes
_QUOTE = r'["″“”]?'      # optional " ″ " "
_FT    = r"['′’]?"             # optional ' ′ '
SCALE_PATTERN = re.compile(
    r'(?:SCALE[:\s]+)?'                                    # optional "SCALE:" prefix
    rf'(\d+(?:/\d+)?(?:\.\d+)?)\s*{_QUOTE}\s*[=—]\s*' # drawn measurement
    rf'(\d+(?:\.\d+)?)\s*{_FT}',                           # real measurement
    re.IGNORECASE,
)
```

Ratio-format scales (`1:48`, `1:96` — engineering) remain out of
scope; a follow-up sprint owns them if needed.

### Scale detection cascade

`PDFParser._detect_scale()` runs in `load()` after `fitz.open()`
succeeds and sets three observable fields:

1. **Manual override** — if `manual_scale` is non-None and parses
   via `_parse_scale_string`, set `scale_source = "manual"`. Bad
   manual strings log a warning and fall through (don't crash).
2. **Auto-detect from page 0** — `doc[0].get_text()` returns the
   PDF's raw text. Search via `SCALE_PATTERN` (case-insensitive,
   matches `SCALE:`, `Scale:`, `SCALE`, optional whitespace, the
   drawn measurement, `=`, the real measurement). Parse. On hit,
   `scale_source = "auto_text"`.
3. **Fallback** — `scale_in_per_pt` stays at the 1:1 default
   (`1/72`), `scale_source = "unknown"`, `scale_warning` populated
   with an actionable message including the `manual_scale`
   parameter name.

### Path walking — handle three item shapes

`_convert_path_to_walls` is rewritten to handle:

| Item shape | Meaning | Action |
|---|---|---|
| `("m", p)` | Move-to | Set `current_point = p` |
| `("l", p1, p2)` | Explicit line (newer PyMuPDF) | Add wall (p1 → p2); `current_point = p2` |
| `("l", p)` | Line-to from current_point (older) | Skip if `current_point is None`; else add wall; `current_point = p` |
| `("re", rect)` | Rectangle | Unpack 4 corners into 4 walls (clockwise) |
| anything else | Skip (curves, color, etc.) | |

### Length filter

Replace `if wall.length > 5` (raw PDF points) with
`if wall.length_inches >= MIN_WALL_LENGTH_IN` where the constant
defaults to `1.0` (real-world inch). This is the tightest cutoff
that still filters typical hatch fragments and annotation ticks
(sub-tick usually <0.5 in) while preserving legit short
construction segments — jamb returns (3-6 in), wing walls (4-12 in),
corner returns (4-8 in). Constant is named so future tuning is
one-line.

### Backward-compat for existing callers

- `PDFParser(file_path)` (no `manual_scale`) on a PDF with no
  detectable scale → behaves like today's bug: 1:1 fallback,
  numbers off by the scale factor. **Critical**: now the
  `scale_warning` field tells you why.
- DXF / raster code paths: unchanged. The fix is local to
  `pdf_parser.py` and the one-line `pdf_takeoff.py` wiring.
- API consumers querying `result.metadata` get the new
  `pdf_scale_source` and `pdf_scale_warning` fields when the PDF
  branch ran — observable but additive.

## Sample Implementation

(See the conversation-history sample for the canonical shape; the
spec captures the architectural decisions baked in.)

Key skeleton:

```python
# backend/app/core/parsers/pdf_parser.py

import re
from typing import Optional
import fitz
from app.core.cv.dimension_parser import DimensionParseError, _parse_fraction

SCALE_PATTERN = re.compile(
    r'SCALE[:\s]+(\d+(?:/\d+)?(?:\.\d+)?)\s*"?\s*=\s*(\d+(?:\.\d+)?)\s*\'',
    re.IGNORECASE,
)


def _parse_scale_string(s: str) -> float:
    """Convert a `1/4"=1'-0"` style scale into ``inches per PDF point``."""
    m = re.match(r'(\d+(?:/\d+)?(?:\.\d+)?)\s*"?\s*=\s*(\d+(?:\.\d+)?)\s*\'?', s.strip())
    if not m:
        raise DimensionParseError(f"unparseable scale: {s!r}")
    drawn_in = _parse_fraction(m.group(1))
    real_ft = float(m.group(2))
    return (real_ft * 12.0) / (drawn_in * 72.0)


class PDFParser:
    def __init__(self, file_path, manual_scale: Optional[str] = None):
        self.file_path = Path(file_path)
        self.doc: Optional[fitz.Document] = None
        self.walls: list = []
        self.texts: list = []
        self._manual_scale = manual_scale
        self.scale_in_per_pt: float = 1.0 / 72.0   # 1:1 fallback
        self.scale_source: str = "unknown"
        self.scale_warning: Optional[str] = None

    def load(self) -> bool:
        try:
            self.doc = fitz.open(str(self.file_path))
        except Exception as e:
            logger.error("PDF load failed: %s", e)
            return False
        self._detect_scale()
        return True

    def _detect_scale(self) -> None:
        if self._manual_scale:
            try:
                self.scale_in_per_pt = _parse_scale_string(self._manual_scale)
                self.scale_source = "manual"
                return
            except DimensionParseError:
                logger.warning("manual_scale %r unparseable; trying auto-detect",
                               self._manual_scale)
        if self.doc and len(self.doc):
            text = self.doc[0].get_text()
            m = SCALE_PATTERN.search(text)
            if m:
                try:
                    self.scale_in_per_pt = _parse_scale_string(
                        f'{m.group(1)}"={m.group(2)}\''
                    )
                    self.scale_source = "auto_text"
                    return
                except DimensionParseError:
                    pass
        self.scale_warning = (
            "Could not detect drawing scale; falling back to 1:1 PDF points. "
            "Wall lengths will be wrong for any drawing not at 1:1. Pass "
            "`manual_scale` (e.g., `1/4\"=1'-0\"`) to override."
        )

    # _convert_path_to_walls handles m/l/re items; see sample in conversation.
```

```python
# backend/app/core/pdf_takeoff.py (one-line wiring change)
pdf = PDFParser(file_path, manual_scale=manual_scale)
```

## Edge Cases & Error Handling

### PDF with no parseable scale text AND no manual override
- **Scenario**: a CAD-exported PDF whose title block uses a custom
  format the SCALE_PATTERN doesn't match
- **Behavior**: `scale_source = "unknown"`, `scale_warning`
  populated. Walls extract at 1:1 (wrong but produced); downstream
  takeoff continues; the warning is the contract for "trust the
  shape, not the LF."
- **Test**: AC-3

### Manual override is malformed (typo)
- **Scenario**: user passes `manual_scale="1/4 = 1-0"` (missing
  quotes and apostrophe)
- **Behavior**: log warning at `_detect_scale`; fall through to
  auto-detect; if that also fails, fall through to 1:1
- **Test**: AC-5

### PyMuPDF emits `("l", p1, p2)` items
- **Scenario**: real CAD-exported PDF using the newer item shape
- **Behavior**: parser produces one wall per line item
- **Test**: AC-6

### PyMuPDF emits `("m", p1); ("l", p2)` items
- **Scenario**: an older-style PDF emitting move-then-line pairs
- **Behavior**: parser produces one wall per line item; `current_point`
  tracks correctly
- **Test**: AC-7

### Rectangle item in path
- **Scenario**: a CAD tool emits `("re", Rect)` for a room outline
- **Behavior**: parser unpacks the rectangle into 4 walls (top,
  right, bottom, left)
- **Test**: AC-8

### Lonely line-to with no prior move-to
- **Scenario**: an `("l", p)` item appears before any `("m", p)`
- **Behavior**: skipped (no `current_point` to anchor to);
  `current_point` stays None
- **Test**: AC-9

### Cubic-bezier `("c", ...)` items
- **Scenario**: curves in the path
- **Behavior**: skipped; `current_point` updated to the curve's end
  point (item index per PyMuPDF docs) so subsequent `("l", p)` items
  still resolve
- **Test**: AC-10

### Length filter at boundary (0.99 in, 1.00 in, 1.01 in)
- **Scenario**: real-world wall length right at the threshold
- **Behavior**: ≥ 1.0 keeps; < 1.0 drops
- **Test**: AC-11 parametric

### PyMuPDF doc fails to open
- **Scenario**: corrupted file with `.pdf` extension
- **Behavior**: `load()` returns False; `scale_*` fields stay at
  defaults; downstream `run_pdf_takeoff` raises `RuntimeError`
  (Sprint 4e contract, unchanged)
- **Test**: existing Sprint 4e AC-8 still holds

### `_parse_scale_string` rejects `"1:48"` ratio format
- **Scenario**: user provides a ratio scale like `"1:48"` (common
  in engineering drawings) instead of architectural `"1/4\"=1'"`
- **Behavior**: explicitly out of scope this sprint; logs a warning
  and falls through to 1:1
- **Test**: AC-12

## Acceptance Criteria

### AC-1: `_parse_scale_string` converts standard architectural scales
- **Given** a string `1/4"=1'-0"`
- **When** `_parse_scale_string` runs
- **Then** the returned value is `12.0/(0.25*72) ≈ 0.6667`
  inches-per-PDF-point
- **And** the same logic handles `1/8"=1'`, `3/16"=1'`, `1/2"=1'`

### AC-2: Auto-detected scale beats no-scale
- **Given** a PDF whose page-0 text contains `SCALE: 1/4"=1'-0"`
- **When** `PDFParser.load()` runs
- **Then** `scale_source == "auto_text"`,
  `scale_warning is None`, and `scale_in_per_pt` matches AC-1

### AC-3: Unknown scale populates the warning
- **Given** a PDF with no scale annotation text AND no manual
  override
- **When** `PDFParser.load()` runs
- **Then** `scale_source == "unknown"`, `scale_warning` is a
  non-empty string mentioning `manual_scale`,
  `scale_in_per_pt == 1.0/72.0`

### AC-4: Manual override beats auto-detect
- **Given** a PDF whose page-0 text contains `SCALE: 1/8"=1'-0"`
  AND `manual_scale="1/4\"=1'-0\""`
- **When** `PDFParser.load()` runs
- **Then** `scale_source == "manual"` and `scale_in_per_pt`
  matches the manual value (not the auto-detected one)

### AC-5: Malformed manual override falls through to auto-detect
- **Given** `manual_scale="not-a-scale"` AND a PDF with parseable
  page-0 text
- **When** `PDFParser.load()` runs
- **Then** `scale_source == "auto_text"`, no crash, a warning was
  logged

### AC-6: Path-walking handles `("l", p1, p2)` items
- **Given** a synthetic page with explicit line items emitting
  `("l", p1, p2)`
- **When** `extract_walls()` runs
- **Then** the parser produces one `PDFWallElement` per line item

### AC-7: Path-walking handles `("m", p1); ("l", p2)` sequences
- **Given** a synthetic page emitting move-then-line pairs
- **When** `extract_walls()` runs
- **Then** the parser produces one wall per line item with
  endpoints derived from the prior `current_point`

### AC-8: Rectangles unpack into 4 walls
- **Given** a synthetic page emitting `("re", Rect(0,0,10,5))`
- **When** `extract_walls()` runs
- **Then** the parser produces 4 walls forming the rectangle's
  perimeter

### AC-9: Lonely line-to without prior move-to is skipped
- **Given** a page whose first item is `("l", p)` with no prior
  `("m", *)`
- **When** `extract_walls()` runs
- **Then** the line is skipped; no wall produced; subsequent items
  still process

### AC-10: Cubic-bezier items advance current_point without producing a wall
- **Given** a page with `("m", p1); ("c", ctrl1, ctrl2, p_end);
  ("l", p_target)`
- **When** `extract_walls()` runs
- **Then** the curve produces no wall, `current_point` advances
  to `p_end`, and the subsequent line produces a wall from
  `p_end → p_target`

### AC-11: Length filter is parametrized by real-world inches
- **Given** walls at real-world lengths in `{0.99, 1.00, 1.01,
  100.0}` inches
- **When** the filter runs
- **Then** `0.99` is dropped; the other three are kept

### AC-12: `PDFWallElement.length_inches` honors `scale_in_per_pt`
- **Given** a `PDFParser` with `scale_in_per_pt = 0.6667` (i.e.,
  1/4"=1') and a wall with `start=(0,0)`, `end=(36, 0)` (36 PDF
  points)
- **When** `length_inches` is read
- **Then** the value is `36 × 0.6667 ≈ 24.0` real-world inches
  (which equals 2 ft, matching what a 36-PDF-point wall would be
  on a 1/4"=1'-0" drawing)

### AC-13: `run_pdf_takeoff` threads `manual_scale` into PDFParser
- **Given** `run_pdf_takeoff(file_path, manual_scale="1/4\"=1'-0\"", ...)`
- **When** the helper instantiates the PDFParser
- **Then** the parser's `scale_source == "manual"`

### AC-14: Path-walking handles the documented item-shape set
- **Given** synthetic pages emitting each of the item shapes
  characterized during the pre-implement Vermont spike (see Phase 0
  below) — `("m", p)`, `("l", p)`, `("l", p1, p2)`, `("re", rect)`,
  plus any additional shapes the spike surfaces
- **When** `extract_walls()` runs
- **Then** each item shape produces the expected wall(s) per the
  handling table above; unhandled shapes are documented as skipped
  with no crash

### AC-15: Vermont smoke fixture activates when its shapes are covered
- **Given** Vermont-Microhouse PDF + the Sprint 4f parser AFTER
  the spike's shape set is implemented
- **When** the e2e dispatch runs Vermont
- **Then** `len(walls) > 0` (smoke contract); `pdf_scale_source`
  and `pdf_scale_warning` fields populated in metadata
- **Note**: LF accuracy is not gated; Vermont remains smoke-only.
- **Fallback**: if Vermont uses item shapes outside what the spike
  characterized, activation is deferred to a follow-up ticket
  capturing the specific unhandled shape. Sprint 4f still ships;
  the harness + wiring stand.

### AC-16: ≥80% line coverage on `pdf_parser.py` + regression
- **Given** the implementation is complete
- **When** the test suite runs with coverage
- **Then** `app.core.parsers.pdf_parser` has ≥80% line coverage
- **And** the prior 293 Sprint 2/3/4/5 tests still pass
- **And** ruff is clean

## Technical Notes

- **Affected files:**
  - `backend/app/core/parsers/pdf_parser.py` — scale detection,
    path-walking rewrite, length filter
  - `backend/app/core/pdf_takeoff.py` — pass `manual_scale` into
    `PDFParser(file_path, manual_scale=...)`
  - `backend/tests/test_pdf_parser.py` (new — none exists today) —
    unit tests covering AC-1 through AC-12
  - `backend/tests/integration/test_phase1_e2e.py` — Vermont
    fixture activated; references.json updated; smoke contract
    asserted
  - `backend/tests/fixtures/phase1/references.json` — add Vermont
    entry as `role: "smoke"`, `kind: "pdf"`
  - `backend/tests/fixtures/phase1/vector_pdf_vermont.pdf` — re-add
    bundled fixture (was removed during Sprint 5 cleanup)
  - `.github/workflows/ci.yml` — add `tests/test_pdf_parser.py` +
    `--cov=app.core.parsers.pdf_parser`

- **Test strategy:**
  - Synthetic PDFs built in-memory via `fitz.open()` +
    `doc.new_page()`. Use `Shape` API to emit specific item shapes
    deterministically.
  - For scale auto-detect: synthesize PDFs with embedded text
    blocks via `page.insert_text(...)`.
  - For path-walking: monkeypatch `PDFParser._fitz_page_drawings`
    (new seam — wraps `page.get_drawings()`) to feed controlled
    item lists. This avoids depending on PyMuPDF version-specific
    output for unit tests.
  - For Vermont: bundled fixture flows through real PyMuPDF;
    smoke contract.

- **Patterns to follow:** mirror Sprint 4e's defensive seam pattern
  (the `image_loader` callable seam in `RasterParser`) — wrap
  PyMuPDF calls in injectable seams so tests don't depend on
  specific PyMuPDF behaviors.

- **Dependencies:** PyMuPDF already in deps. Reuses
  `dimension_parser._parse_fraction` for fraction string parsing.

## Dependencies

- Sprint 4e VERIFIED. (Done.)
- `app.core.cv.dimension_parser` for `_parse_fraction` reuse.

## Open Questions

- **Ratio-format scales (`1:48`)** — explicitly out of scope; if
  user-provided fixtures show this is needed, follow-up sprint.
- **Multi-page scale detection** — Sprint 4f detects from page 0
  only. If real-world plans frequently use per-page scales, a
  future sprint extends detection to per-page.
- **Vermont reference numbers** — Sprint 4f only enables Vermont as
  a smoke fixture. Hand-counted reference for a gated Vermont is
  user work (when user provides ground-truth fixtures).
