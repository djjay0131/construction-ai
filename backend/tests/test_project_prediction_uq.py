"""
Tests for project_prediction_uq.py — RD-2 Sobol sanity bounds and
RD-5 determinism snapshot.

Run from `backend/`:
    pytest tests/test_project_prediction_uq.py -v
"""
from __future__ import annotations

import json
import os
import sys
from typing import Dict

import numpy as np
import pytest


# Make the structural module importable. We bypass `app.core.structural`
# because the module relies on a sibling `from beam_solver import ...` that
# is only resolvable from inside its own directory.
_STRUCTURAL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "app", "core", "structural",
)
sys.path.insert(0, _STRUCTURAL_DIR)


@pytest.fixture(scope="module")
def puq():
    """Import the module under test once per test module."""
    import project_prediction_uq as m
    return m


# ---------------------------------------------------------------------------
# RD-2: Sobol sanity-bound assertion
# ---------------------------------------------------------------------------

class TestSobolIndices:
    """Tests for run_sobol_indices() — RD-2."""

    def test_returns_expected_keys(self, puq):
        res = puq.run_sobol_indices(n_base=128, seed=42)
        assert set(res.keys()) >= {
            "S1", "ST", "labels", "n_base", "n_calls",
            "var_y", "S1_sum", "ST_sum", "interaction",
        }
        assert res["labels"] == ["E", "q0"]

    def test_n_calls_equals_4_n_base(self, puq):
        res = puq.run_sobol_indices(n_base=128, seed=42)
        assert res["n_calls"] == 128 * 4

    def test_S1_and_ST_have_two_entries(self, puq):
        res = puq.run_sobol_indices(n_base=128, seed=42)
        assert res["S1"].shape == (2,)
        assert res["ST"].shape == (2,)

    def test_var_y_strictly_positive(self, puq):
        res = puq.run_sobol_indices(n_base=128, seed=42)
        assert res["var_y"] > 0

    def test_ST_within_sanity_bounds_at_default_n(self, puq):
        """RD-2: at n_base=1024 (production setting), ST values must
        lie in [SOBOL_SANITY_LO, SOBOL_SANITY_HI] for both inputs."""
        res = puq.run_sobol_indices(n_base=1024, seed=42)
        for label, st in zip(res["labels"], res["ST"]):
            assert puq.SOBOL_SANITY_LO <= st <= puq.SOBOL_SANITY_HI, (
                f"ST[{label}]={st} outside sanity bounds"
            )

    def test_ST_sum_close_to_unity_for_additive_dominant_model(self, puq):
        """For w_max ∝ q0/E (multiplicative but weakly interacting at the
        chosen ranges), ΣST should be close to 1 + small interaction."""
        res = puq.run_sobol_indices(n_base=1024, seed=42)
        assert 0.95 < res["ST_sum"] < 1.10

    def test_S1_sum_close_to_unity(self, puq):
        res = puq.run_sobol_indices(n_base=1024, seed=42)
        assert 0.95 < res["S1_sum"] < 1.05

    def test_interaction_non_negative(self, puq):
        """ΣST ≥ ΣS1 always (ST captures interactions); MC noise can flip
        the sign by a tiny margin, so allow a small negative tolerance."""
        res = puq.run_sobol_indices(n_base=1024, seed=42)
        assert res["interaction"] > -0.02

    def test_deterministic_across_two_runs(self, puq):
        """Running twice with the same seed must produce identical output
        (catches any RNG-state contamination across calls)."""
        a = puq.run_sobol_indices(n_base=256, seed=42)
        b = puq.run_sobol_indices(n_base=256, seed=42)
        np.testing.assert_array_equal(a["S1"], b["S1"])
        np.testing.assert_array_equal(a["ST"], b["ST"])
        assert a["var_y"] == b["var_y"]

    def test_different_seed_gives_different_result(self, puq):
        """Sanity check that seed actually matters (otherwise a frozen RNG
        somewhere would silently invalidate the determinism guarantee)."""
        a = puq.run_sobol_indices(n_base=256, seed=42)
        b = puq.run_sobol_indices(n_base=256, seed=123)
        # At least one element should differ noticeably
        assert not np.allclose(a["S1"], b["S1"], atol=1e-6)

    def test_sanity_bound_violation_raises(self, puq, monkeypatch):
        """RD-2: when ST falls outside [LO, HI], RuntimeError with
        a clear message must be raised."""
        # Tighten the bound so that legitimate output triggers the assertion
        monkeypatch.setattr(puq, "SOBOL_SANITY_LO", 0.99)
        monkeypatch.setattr(puq, "SOBOL_SANITY_HI", 1.00)
        with pytest.raises(RuntimeError, match="sanity-bound"):
            puq.run_sobol_indices(n_base=128, seed=42)

    def test_saltelli_construction_recovers_both_inputs(self, puq):
        """Regression test for the bug where two independent
        sampler.random(n_base) calls produced correlated Sobol
        continuations that drove ST[E] → 0. The current implementation
        draws a single Sobol sequence in d=4 and splits A|B. After the
        fix both inputs must show ST > 0.10 (well above the noise floor)
        — pre-fix the value was ~0.0004."""
        res = puq.run_sobol_indices(n_base=512, seed=42)
        assert res["ST"][0] > 0.10, (
            f"ST[E]={res['ST'][0]:.4f} too small — possible regression of "
            f"the correlated-Sobol-sequence bug"
        )
        assert res["ST"][1] > 0.10, (
            f"ST[q0]={res['ST'][1]:.4f} too small — possible regression"
        )

    def test_q0_alone_dominates_when_E_held_fixed_in_spec(self, puq):
        """Sanity check: if the model were entirely insensitive to E we'd
        expect S_T[E] ≪ S_T[q0]. The fact that S_T[E] and S_T[q0] are
        within a factor of ~1.3 of each other validates the
        physically-expected near-balance for w_max ∝ q0/E with similar
        input CoVs."""
        res = puq.run_sobol_indices(n_base=1024, seed=42)
        ratio = max(res["ST"]) / min(res["ST"])
        assert ratio < 2.0, (
            f"S_T ratio {ratio:.2f} too large — one input wrongly "
            f"dominates given comparable CoVs (E=10%, q0~11.5%)"
        )


# ---------------------------------------------------------------------------
# RD-5: Determinism snapshot
# ---------------------------------------------------------------------------

class TestSnapshot:
    """Tests for build_snapshot, _flatten, compare_against_snapshot — RD-5."""

    def test_flatten_handles_nested_dict(self, puq):
        out: Dict[str, float] = {}
        puq._flatten("", {"a": {"b": 1.5, "c": [2.0, 3.0]}}, out)
        assert out == {"a.b": 1.5, "a.c[0]": 2.0, "a.c[1]": 3.0}

    def test_flatten_skips_strings(self, puq):
        out: Dict[str, float] = {}
        puq._flatten("", {"label": "hello", "value": 42.0}, out)
        assert "label" not in out
        assert out["value"] == 42.0

    def test_flatten_skips_booleans(self, puq):
        out: Dict[str, float] = {}
        puq._flatten("", {"flag": True, "value": 1.0}, out)
        assert "flag" not in out
        assert out["value"] == 1.0

    def test_compare_writes_baseline_when_missing(self, puq, tmp_path):
        path = tmp_path / "snapshot.json"
        snap = {"a": 1.0, "b": [2.0, 3.0]}
        puq.compare_against_snapshot(snap, path=str(path))
        assert path.exists()
        with open(path) as f:
            written = json.load(f)
        assert written == snap

    def test_compare_passes_within_tolerance(self, puq, tmp_path):
        path = tmp_path / "snapshot.json"
        with open(path, "w") as f:
            json.dump({"a": 1.0, "b": 2.0}, f)
        # Slight drift within tolerance — should not raise
        puq.compare_against_snapshot({"a": 1.0 + 1e-7, "b": 2.0},
                                     path=str(path), atol=1e-5)

    def test_compare_raises_on_drift_above_tolerance(self, puq, tmp_path):
        path = tmp_path / "snapshot.json"
        with open(path, "w") as f:
            json.dump({"a": 1.0, "b": 2.0}, f)
        with pytest.raises(RuntimeError, match="determinism check FAILED"):
            puq.compare_against_snapshot({"a": 1.5, "b": 2.0},
                                         path=str(path), atol=1e-5)

    def test_compare_raises_on_missing_field(self, puq, tmp_path):
        path = tmp_path / "snapshot.json"
        with open(path, "w") as f:
            json.dump({"a": 1.0, "b": 2.0}, f)
        with pytest.raises(RuntimeError, match="determinism check FAILED"):
            puq.compare_against_snapshot({"a": 1.0},
                                         path=str(path), atol=1e-5)

    def test_compare_ignores_metadata_fields(self, puq, tmp_path):
        path = tmp_path / "snapshot.json"
        with open(path, "w") as f:
            json.dump({"a": 1.0, "tolerance": 0.99,
                      "schema_version": 1}, f)
        # Should NOT raise even though tolerance + schema_version differ
        puq.compare_against_snapshot({"a": 1.0, "tolerance": 1e-5,
                                      "schema_version": 99},
                                     path=str(path), atol=1e-5)


# ---------------------------------------------------------------------------
# fig5_sobol_indices smoke test
# ---------------------------------------------------------------------------

class TestFig5:
    """Lightweight smoke tests for fig5_sobol_indices — verifies the figure
    is generated to disk without raising; visual content is reviewed manually
    (per AC-2)."""

    def test_fig5_produces_pdf_and_png(self, puq, tmp_path, monkeypatch):
        monkeypatch.setattr(puq, "OUTPUT_DIR", str(tmp_path))
        # Use a small, fast Sobol run
        sobol_res = puq.run_sobol_indices(n_base=64, seed=42)
        puq.fig5_sobol_indices(sobol_res)
        assert (tmp_path / "fig5_sobol.pdf").exists()
        assert (tmp_path / "fig5_sobol.png").exists()


# ---------------------------------------------------------------------------
# print_sobol_table smoke test
# ---------------------------------------------------------------------------

class TestPrintSobolTable:
    def test_table_contains_input_labels_and_indices(self, puq, capsys):
        sobol_res = puq.run_sobol_indices(n_base=64, seed=42)
        puq.print_sobol_table(sobol_res)
        out = capsys.readouterr().out
        assert "Sobol" in out
        assert "S_1" in out and "S_T" in out
        assert "E" in out and "q0" in out
