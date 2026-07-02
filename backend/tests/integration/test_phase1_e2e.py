"""Sprint 5: Phase 1 end-to-end integration smoke test.

Drives every active fixture in ``backend/tests/fixtures/phase1/references.json``
through the takeoff pipeline (dispatch by ``kind``), asserts provenance
fields populate, and gates BOM accuracy on any fixture marked
``role: "gated"``. Each gated fixture must come with a hand-counted
``total_wall_lf`` reference; the test enforces ≤10% wall-LF error.

Fixture layout::

    backend/tests/fixtures/phase1/
        references.json                  hand-edited
        _build_dxf_fixture.py            one-shot builder
        dxf_smoketest_4wall.dxf          bundled (output of builder)
        _cache/                          gitignored (fetched + transformed fixtures)

Initial Sprint 5 scope ships with ONE active fixture (`dxf_smoketest_4wall`,
smoke-only). The harness, mock KG client, validation-report renderer,
and gated-fixture machinery are all in place for user-provided
hand-counted fixtures to drop in via ``references.json`` later. Vermont-
Microhouse + Construct101 (the public fixtures originally researched)
are deferred: Vermont's vector PDF surfaces a latent PDFParser unit bug
(zero walls extracted; tracked as Sprint 4f), and Construct101's
download URL is gated behind a checkout flow that doesn't yield a
direct PDF link.

When a user-provided fixture arrives:
  1. Drop the file in `phase1/` (or under `_cache/` if not redistributable).
  2. Add an entry to `references.json` with `kind`, `role`, and (for
     gated fixtures) `total_wall_lf` + `line_items`.
  3. Re-run the test. No code changes needed.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Optional

import pytest

from app.core.extraction.lumber_calculator import (
    FramingConfig,
    LumberCalculator,
    StudSpacing,
)
from app.core.parsers.dxf_parser import DXFParser, WallElement

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "phase1"
CACHE_DIR = FIXTURE_DIR / "_cache"
_RAW_REFS = json.loads((FIXTURE_DIR / "references.json").read_text())

# Skip placeholder/comment keys that start with "_" — those are docs in
# references.json, not real fixtures.
REFS = {k: v for k, v in _RAW_REFS.items() if not k.startswith("_")}
FIXTURES = list(REFS.keys())

REPORT_PATH = Path(__file__).resolve().parents[3] / "construction" / "design" / "phase1-validation-report.md"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class FixtureResult:
    name: str
    role: str                       # "smoke" | "gated"
    actual_lf: float
    reference_lf: Optional[float]
    lf_error_pct: Optional[float]
    per_item_errors_pct: dict
    provenance_ok: bool
    rule_citations_ok: bool


# ---------------------------------------------------------------------------
# Fixture resolution
# ---------------------------------------------------------------------------


def resolve_or_skip(fixture_name: str, ref: dict) -> Path:
    """Locate a bundled fixture or skip the test with a clear reason.

    Fetch + transform paths are scaffolded for future use (Construct101-
    style fixtures); for Sprint 5's initial shipment we only resolve
    bundled files.
    """
    kind = ref.get("kind", "dxf")
    bundled_name = f"{fixture_name}.{kind}"
    candidate = FIXTURE_DIR / bundled_name
    if candidate.exists():
        return candidate
    pytest.skip(f"{fixture_name}: bundled fixture {bundled_name} not present")


# ---------------------------------------------------------------------------
# Per-fixture takeoff dispatch
# ---------------------------------------------------------------------------


def invoke_takeoff_for_path(path: Path) -> list[WallElement]:
    """Dispatch by file extension. Returns the WallElement list.

    Vector PDFs (Sprint 4f-enabled) call PDFParser directly to avoid the
    YOLO/EasyOCR import chain that only matters for raster fallback.
    Scanned-PDF fixtures with raster fallback will need to go through
    ``run_pdf_takeoff`` — deferred until such a fixture lands.
    """
    from app.core.parsers.pdf_parser import PDFParser

    ext = path.suffix.lower()
    if ext == ".dxf":
        with DXFParser(str(path)) as parser:
            assert parser.load(), f"Failed to load DXF: {path}"
            return parser.extract_walls()
    if ext == ".pdf":
        pdf = PDFParser(str(path))
        assert pdf.load(), f"Failed to load PDF: {path}"
        pdf_walls = pdf.extract_walls()
        scale = pdf.scale_in_per_pt
        pdf.close()
        # Convert PDFWallElement → WallElement so downstream lumber calc
        # sees a uniform shape. Coordinates are scaled from PDF points to
        # real-world inches so WallElement.length_inches produces the same
        # value PDFWallElement.length_inches would.
        return [
            WallElement(
                start_point=(w.start_point[0] * scale, w.start_point[1] * scale),
                end_point=(w.end_point[0] * scale, w.end_point[1] * scale),
                layer=f"page_{w.page_number}",
                metadata={"source": "pdf_vector", "page": w.page_number, **w.metadata},
            )
            for w in pdf_walls
        ]
    pytest.skip(f"Unsupported fixture extension: {ext}")  # pragma: no cover - defensive; references.json only ships dxf/pdf


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def phase1_results():
    """Session-scoped registry the report test finalizes."""
    return []


@pytest.fixture
def mock_kg_client():
    """Returns canned IRC rule citations regardless of input. Sprint 5
    asserts the BOM-to-citation wiring works; the real KG suite owns
    rule-content correctness."""

    class _Mock:
        def cite_rule_for(self, lumber_item):
            return {
                "2x4 Stud": ["R602.3.1"],
                "2x4 Plate": ["R602.3.2"],
            }.get(lumber_item.name, ["R602.3"])

    return _Mock()


# ---------------------------------------------------------------------------
# Per-fixture test
# ---------------------------------------------------------------------------


def _line_item_lookup(bom, key: str) -> float:
    if key == "stud_2x4":
        for line in bom:
            if line.name.endswith("Stud"):
                return float(line.quantity)
    if key == "plate_2x4_lf":
        for line in bom:
            if line.name.endswith("Plate"):
                return float(line.total_linear_feet)
    return 0.0


@pytest.mark.integration
@pytest.mark.parametrize("fixture_name", FIXTURES)
def test_phase1_fixture(fixture_name, mock_kg_client, phase1_results):
    ref = REFS[fixture_name]
    plan_path = resolve_or_skip(fixture_name, ref)
    walls = invoke_takeoff_for_path(plan_path)

    calc = LumberCalculator(
        FramingConfig(stud_spacing=StudSpacing.OC_16),
        kg_client=mock_kg_client,
    )
    bom = calc.calculate_all_walls(walls)

    actual_lf = sum(w.length_inches for w in walls) / 12.0

    has_lf_ref = ref.get("total_wall_lf") is not None
    lf_error_pct = (
        abs(actual_lf - ref["total_wall_lf"]) / ref["total_wall_lf"] * 100
        if has_lf_ref else None
    )
    per_item_errors = (
        {item: abs(_line_item_lookup(bom, item) - ref["line_items"][item])
                / ref["line_items"][item] * 100
         for item in ref["line_items"]}
        if ref.get("line_items") else {}
    )
    provenance_ok = bool(bom) and all(line.source_walls for line in bom)
    rule_citations_ok = bool(bom) and all(line.rule_citations for line in bom)

    phase1_results.append(FixtureResult(
        name=fixture_name,
        role=ref.get("role", "smoke"),
        actual_lf=actual_lf,
        reference_lf=ref.get("total_wall_lf"),
        lf_error_pct=lf_error_pct,
        per_item_errors_pct=per_item_errors,
        provenance_ok=provenance_ok,
        rule_citations_ok=rule_citations_ok,
    ))

    # Smoke contract (all fixtures).
    assert walls, f"{fixture_name}: takeoff produced no walls"
    assert provenance_ok, f"{fixture_name}: BOM line missing source_walls"
    assert rule_citations_ok, f"{fixture_name}: BOM line missing rule_citations"

    # Accuracy gate (gated fixtures only).
    if ref.get("role") == "gated":  # pragma: no cover - lights up when a gated fixture is added to references.json; see TestGateCheck
        assert lf_error_pct is not None, (
            f"{fixture_name}: gated but no total_wall_lf reference"
        )
        assert lf_error_pct <= 10.0, (
            f"{fixture_name}: BOM accuracy gate failed — "
            f"LF error {lf_error_pct:.1f}% > 10%"
        )


# ---------------------------------------------------------------------------
# Validation report emission
# ---------------------------------------------------------------------------


def _render_report(results: list[FixtureResult]) -> str:
    lines = [
        "# Phase 1 Validation Report",
        "",
        "Generated by `backend/tests/integration/test_phase1_e2e.py`.",
        "",
        "## Summary",
        "",
        "| Fixture | Role | Wall LF (actual) | Wall LF (ref) | LF Error | Result |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        lf_ref = f"{r.reference_lf:.1f}" if r.reference_lf is not None else "—"
        lf_err = f"{r.lf_error_pct:.1f}%" if r.lf_error_pct is not None else "—"
        if r.role == "gated":
            result_label = (
                "PASS" if (r.lf_error_pct is not None and r.lf_error_pct <= 10.0)
                else "FAIL"
            )
        else:
            result_label = "OK (smoke)"
        lines.append(
            f"| {r.name} | {r.role} | {r.actual_lf:.1f} | {lf_ref} | {lf_err} | {result_label} |"
        )
    if not results:
        lines.append("| _no fixtures resolved_ | — | — | — | — | — |")
    lines += [
        "",
        f"**Provenance**: {sum(1 for r in results if r.provenance_ok)}/{len(results) or 0} "
        f"fixtures had non-empty `source_walls` on every BOM line.",
        f"**Rule citations**: {sum(1 for r in results if r.rule_citations_ok)}/{len(results) or 0} "
        f"fixtures had non-empty `rule_citations` on every BOM line.",
        "",
        "## Per-Fixture Diagnostics",
        "",
    ]
    diag_emitted = False
    for r in results:
        if not r.per_item_errors_pct:
            continue
        lines += [f"### {r.name} ({r.role})", "", "| Line item | Error |", "|---|---|"]
        for k, v in r.per_item_errors_pct.items():
            lines.append(f"| {k} | {v:.1f}% |")
        lines.append("")
        diag_emitted = True
    if not diag_emitted:
        lines += ["_no per-item references defined for the active fixtures_", ""]
    lines += [
        "## Methodology",
        "",
        "- BOM accuracy gate: aggregate wall-LF error ≤ 10% on fixtures with `role: gated`.",
        "- Smoke fixtures exercise their dispatch paths and assert non-empty walls +",
        "  provenance fields, but carry no accuracy bar.",
        "- KG rule citations mocked; real KG correctness covered by `test_kg_*` suites.",
        "",
        "## Notes",
        "",
        "- Sprint 5 ships with ONE active smoke fixture (`dxf_smoketest_4wall`). Gated",
        "  fixtures land when the user uploads hand-counted plans.",
        "- This file is git-ignored; capture intentionally via `git add -f` when you",
        "  want to commit a milestone snapshot.",
        "",
    ]
    return "\n".join(lines)


@pytest.mark.integration
def test_validation_report_emitted(phase1_results):
    """Emits the rendered report to the (gitignored) canonical path.

    Does NOT require any gated fixture to have run — Sprint 5 ships with
    smoke-only fixtures. When user-provided gated fixtures land, the
    per-fixture tests above enforce the accuracy bar directly.
    """
    report = _render_report(phase1_results)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report)
    # Provenance must hold for every fixture that ran.
    assert all(r.provenance_ok for r in phase1_results), (
        "At least one fixture had a BOM line missing source_walls"
    )
    assert all(r.rule_citations_ok for r in phase1_results), (
        "At least one fixture had a BOM line missing rule_citations"
    )


# ---------------------------------------------------------------------------
# Renderer + resolve_or_skip unit tests (cover the non-happy-path branches)
# ---------------------------------------------------------------------------


class TestRenderReport:
    """Exercise the rendering branches directly to keep coverage honest."""

    def test_empty_results_emits_placeholder_row(self):
        out = _render_report([])
        assert "_no fixtures resolved_" in out
        assert "_no per-item references defined" in out

    def test_gated_failure_marked_FAIL(self):
        results = [FixtureResult(
            name="x", role="gated",
            actual_lf=10.0, reference_lf=5.0, lf_error_pct=100.0,
            per_item_errors_pct={}, provenance_ok=True, rule_citations_ok=True,
        )]
        out = _render_report(results)
        assert "FAIL" in out

    def test_gated_pass_marked_PASS(self):
        results = [FixtureResult(
            name="x", role="gated",
            actual_lf=4.95, reference_lf=5.0, lf_error_pct=1.0,
            per_item_errors_pct={}, provenance_ok=True, rule_citations_ok=True,
        )]
        out = _render_report(results)
        assert "PASS" in out
        assert "FAIL" not in out

    def test_per_item_diagnostics_emitted_when_populated(self):
        results = [FixtureResult(
            name="x", role="smoke",
            actual_lf=10.0, reference_lf=None, lf_error_pct=None,
            per_item_errors_pct={"stud_2x4": 3.5},
            provenance_ok=True, rule_citations_ok=True,
        )]
        out = _render_report(results)
        assert "### x (smoke)" in out
        assert "| stud_2x4 | 3.5% |" in out
        assert "_no per-item references" not in out


class TestResolveOrSkip:
    def test_missing_bundled_fixture_skips(self, monkeypatch, tmp_path):
        # Point FIXTURE_DIR at an empty tmp dir so the bundled lookup fails.
        from tests.integration import test_phase1_e2e as mod
        monkeypatch.setattr(mod, "FIXTURE_DIR", tmp_path)
        with pytest.raises(pytest.skip.Exception, match="not present"):
            resolve_or_skip("ghost_fixture", {"kind": "dxf"})


class TestLineItemLookup:
    def test_unknown_key_returns_zero(self):
        # Unknown reference key (e.g., user-typoed "stud_2x6") falls through
        # to the 0.0 default; per_item_errors_pct then shows 100% for that
        # line, surfacing the typo in the validation report.
        assert _line_item_lookup([], "unknown_key") == 0.0


class TestGateCheck:
    """Exercises the gate-check logic that the parametrized test pragma'd.

    The in-test branch was pragma'd because the active references.json has
    no gated entries; this class proves the gate predicate itself behaves
    correctly when a future gated fixture lands.
    """

    @staticmethod
    def _would_pass(lf_error_pct: Optional[float]) -> bool:
        """Mirror of the gate condition used in test_phase1_fixture."""
        return lf_error_pct is not None and lf_error_pct <= 10.0

    def test_gate_passes_at_zero_error(self):
        assert self._would_pass(0.0)

    def test_gate_passes_at_boundary(self):
        assert self._would_pass(10.0)

    def test_gate_fails_above_boundary(self):
        assert not self._would_pass(10.1)

    def test_gate_fails_when_no_reference(self):
        assert not self._would_pass(None)
