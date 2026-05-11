# Feature: Final Report Pre-Submission Audit and Enhancement

**Status:** VERIFIED (2026-05-04; all four constellize gates pass)
**Date:** 2026-05-03
**Author:** Feature Architect (AI-assisted, constellize:feature:specify)
**Branch:** `Final-report-of-VVUQ` @ 1e03853 (commit hash at audit time)
**Submission deadline:** 2026-05-06 22:00 EST
**Time-to-deadline:** 3 days, 4 nights

## Problem

The CS6444 final-project deliverables on `Final-report-of-VVUQ` are declared "complete"
in `memory-bank/activeContext.md` (2026-04-28). A pre-submission audit against (i) the
instructor's HW2 spec listing the required project topics and (ii) the students' own
HW2 V&V plan reveals **one blocking completeness gap and two major weaknesses** that
will be visible to a reviewer:

1. **Sensitivity analysis is missing.** HW2 (instructor's spec, p.1, paragraph 2) lists
   the required project topics as: *code verification, solution verification, model
   validation, **sensitivity analysis**, and nondeterministic prediction.* The current
   report covers four of five — sensitivity analysis appears only in §7.3 "Future Work"
   (PCE surrogate / Sobol indices listed but not performed).
2. **HW2 V&V plan promises not addressed in the report.** The HW2 plan section
   (`CS6444/HW2/sections/05-vv-plan.tex`) commits to: MMS as a code-verification
   alternative, IRC R602.7 prescriptive comparison, L/240 serviceability check, and a
   Monte Carlo N=10,000 UQ. The report uses Option-2 exact solution (HW3 spec-compliant),
   replaces prescriptive comparison with synthetic CDFs (HW5 Option #2 spec-compliant),
   and replaces N=10,000 MC with Nₑ=25 × Nₐ=100 nested sampling. Each substitution is
   *defensible* but not *defended* in the report prose.
3. **Model-form extrapolation rests on an unargued linearity assumption.** §6.4 fits
   d⁺(q₀) and d⁻(q₀) as linear regressions over five hypothetical validation points
   "assumed proportional to deflection magnitude." The physical argument for
   linear-in-q₀ is plausible (deflection itself is linear in q₀ for a fixed E in the
   exact EB solution) but is not stated.

## Goals

- **G1 (BLOCKING):** Add a §7 "Sensitivity Analysis" section with Sobol first-order (S₁)
  and total-effect (Sᴛ) indices for the two inputs (E, q₀), one new figure, one paragraph
  of interpretation tied to the §7.1 Dominance Analysis. Closes the HW2 instructor spec.
- **G2 (MAJOR):** Add a Discussion-section paragraph reconciling HW2-promised IRC R602.7
  prescriptive comparison with the synthetic-CDF substitution, including an analytical
  sanity check on σ_max and w_max against NDS-2018 grade-1 LVL allowable stress and the
  L/240 + L/360 serviceability limits.
- **G3 (MAJOR):** Add 2-3 sentences to §6.4 justifying the linear-in-q₀ assumption with a
  reference to the q₀-linearity of the EB exact solution.
- **G4-G6 (MINOR):** Strengthen acknowledgments around MMS-vs-exact, synthetic-data
  limitations, χ-vector σ choice, and corner-max U_NUM (standard Roy-Oberkampf practice).
- **G7 (TRIVIAL):** Rename `VVSC_Chuang_ChengShun_Project.tex` to
  `VVSC_Cusati_Chuang_Project.tex` for consistency with the HW2-5 submission convention
  in the proposal repo.
- **G10 (BUILD-BREAKING, surfaced 2026-05-03):** The .tex referenced 8 figures by
  `.pdf` extension (hw3 ×2, hw5 ×2, project ×4) but only `.png` rasters exist for
  those figures on this branch. The .tex did not compile until extensions were
  swapped. Fixed in commit during the audit. Same root cause as the HW4/HW5
  fixes applied to the proposal repo on master last session.
- **Quantitative target:** PDF builds clean, page count grows from 11 to ~12-13 (one new
  section + one new figure + reconciliation paragraph), all references resolve.

## Non-Goals

- **No new physical experiments.** The validation chain remains synthetic per HW5
  Option #2; we strengthen the *acknowledgment* of this limitation, we do not replace
  the data.
- **No alternative beam theory implementation.** Timoshenko, semi-rigid boundaries,
  Kelvin-Voigt creep, Karhunen-Loève random fields all remain in §7.3 Future Work.
- **No re-derivation of nested-sampling methodology.** The Nₑ × Nₐ design is unchanged.
  Sensitivity analysis is added as a *separate* sub-study with its own sampling
  (Saltelli Sobol matrices), not woven into the existing nested loop.
- **No IRC R602.7 table acquisition.** We address the HW2 promise with a
  reconciliation paragraph + analytical sanity check, not a table-by-table comparison.
- **No re-running of HW3-5 standalone scripts.** The aggregated results in the final
  report are taken as-is from the prior commits; only `project_prediction_uq.py` is
  re-run to add the Sobol section.

## User Stories

- As **Jason (submitter)**, I want every HW2 project-topic in the final report so that
  Dr. Roy cannot mark me down for an incomplete deliverable.
- As **a reviewer skimming the report**, I want each major methodological substitution
  (MMS→exact, prescriptive→synthetic, MC→nested) to be explicitly justified so I trust
  the decisions weren't accidental.
- As **the next maintainer**, I want a documented audit trail (this spec) so the
  reasoning behind enhancements survives future edits.

## Design Approach

The audit-and-enhance work splits into two parallel tracks: a **prose track** (G2-G7)
that touches `.tex` only and rebuilds the PDF, and a **code track** (G1) that adds a
new function to `project_prediction_uq.py`, runs it, generates a new figure, and adds
a new section to the `.tex`.

### Track A — Prose-only enhancements (no re-run)

Touches: `backend/app/core/structural/project_report/VVSC_Cusati_Chuang_Project.tex`
(after rename per G7).

| ID | Edit location | Change |
|---|---|---|
| G2 | New paragraph at end of §7.2 "Conservatism Assessment" | "Reconciliation with HW2 V&V Plan" — IRC, L/240 vs L/360, σ_max sanity check |
| G3 | After eq. for d⁺(q₀), d⁻(q₀) in §6.4 | Add 2 sentences citing EB exact solution's q₀-linearity (eq. 2 in §2.2) |
| G4 (MMS) | §3 (Code Verification) intro | One sentence: "MMS was an alternative code-verification approach (HW3 Option 1); Option 2 (closed-form exact) was selected because it exists for the simply-supported uniform-load case (eq. 2)." |
| G5 (synthetic) | §5.1 second paragraph | Tighten: explicitly call out that χ₁/χ₂ vectors are course-prescribed templates, not physically derived; cite Roy 2011 §4 for the practice. |
| G6 (χ σ) | §5.1 (Experimental Datasets) | Justify σ_E = 160,000 psi as ASTM D5456 / NDS Supplement Grade-1 LVL CoV (already cited; tighten one sentence). |
| G7 (filename) | Filename + git mv | `git mv .../VVSC_Chuang_ChengShun_Project.tex .../VVSC_Cusati_Chuang_Project.tex`; update CI workflow + index.html if applicable. |

### Track B — Sensitivity analysis (re-run required)

**File 1:** `backend/app/core/structural/project_prediction_uq.py` — add module:

```python
# ============================================================
# Sensitivity Analysis (Saltelli/Sobol)
# ============================================================

def run_sobol_indices(n_base: int = 1024, seed: int = 42) -> Dict:
    """
    Sobol first-order (S1) and total-effect (ST) indices for w_max(E, q0).

    For the sensitivity decomposition we treat both inputs probabilistically:
        E  ~ N(MU_E, SIG_E)             (4-sigma truncation for bounded support)
        q0 ~ U(Q0_LO, Q0_HI)            (epistemic interval re-cast as uniform)

    This answers 'which input drives output variance' independent of the p-box
    framing used elsewhere in the report. The two analyses answer different
    questions and are not contradictory: the p-box keeps q0 epistemic to bound
    the predictive CDF; Sobol re-casts it probabilistically to rank input
    contributions to total variance.

    Saltelli sample design: total solver calls = n_base * (d + 2) = 4 * n_base.
    With n_base = 1024 -> 4,096 calls at N_GRID = 20 -> seconds of runtime.

    Returns:
        {
          "S1": np.ndarray shape (2,),    # first-order Sobol indices
          "ST": np.ndarray shape (2,),    # total-effect Sobol indices
          "labels": ["E", "q0"],
          "n_calls": int,
          "var_y": float,                 # total output variance (for sanity)
        }
    """
    from scipy.stats import qmc

    rng = np.random.default_rng(seed)
    sampler = qmc.Sobol(d=2, scramble=True, seed=seed)
    A_unit = sampler.random(n_base)
    B_unit = sampler.random(n_base)

    def _rescale(unit_arr):
        out = np.empty_like(unit_arr)
        out[:, 0] = sp_norm.ppf(unit_arr[:, 0], loc=MU_E, scale=SIGMA_E)
        out[:, 1] = Q0_LO + (Q0_HI - Q0_LO) * unit_arr[:, 1]
        return out

    A = _rescale(A_unit); B = _rescale(B_unit)
    f_A = np.array([w_max_solve(*row) for row in A])
    f_B = np.array([w_max_solve(*row) for row in B])

    f_AB = []
    for i in range(2):
        AB = A.copy(); AB[:, i] = B[:, i]
        f_AB.append(np.array([w_max_solve(*row) for row in AB]))

    var_y = np.var(np.concatenate([f_A, f_B]), ddof=1)
    S1 = np.array([np.mean(f_B * (f_AB[i] - f_A)) / var_y for i in range(2)])
    ST = np.array([0.5 * np.mean((f_A - f_AB[i]) ** 2) / var_y for i in range(2)])

    return {"S1": S1, "ST": ST, "labels": ["E", "q0"],
            "n_calls": n_base * 4, "var_y": var_y}


def fig5_sobol_indices(sobol_res: Dict) -> None:
    """Side-by-side bar chart of S1 and ST for E and q0, with sum-check annotation."""
    fig, ax = plt.subplots(1, 1, figsize=(5.0, 3.4))
    labels = sobol_res["labels"]
    x = np.arange(len(labels)); w = 0.35
    ax.bar(x - w/2, sobol_res["S1"], w, label="$S_1$ (first-order)", color="#1f77b4")
    ax.bar(x + w/2, sobol_res["ST"], w, label="$S_T$ (total-effect)", color="#d62728")
    ax.set_xticks(x); ax.set_xticklabels(["$E$", "$q_0$"])
    ax.set_ylabel("Sobol index"); ax.set_ylim(0, 1.05)
    ax.legend(loc="upper right")
    ax.set_title(f"Sobol indices for $w_{{\\max}}$  (n_calls = {sobol_res['n_calls']})")
    _save(fig, "fig5_sobol")
```

Hook into `main()` after the existing nested-sampling stage:

```python
print_header("PHASE 5 — Sensitivity Analysis (Sobol)")
sobol_res = run_sobol_indices(n_base=1024)
print_sobol_table(sobol_res)
fig5_sobol_indices(sobol_res)
```

**File 2:** `.../project_report/VVSC_Cusati_Chuang_Project.tex` — insert new
section between current §7.1 Dominance Analysis and §7.2 Conservatism Assessment:

```latex
\subsection{Sensitivity Analysis}
\label{sec:sensitivity}

Beyond the additive uncertainty budget (Section~\ref{sec:total}), a global
sensitivity analysis quantifies which input drives the variance of $w_{\rm max}$.
Sobol indices are estimated using Saltelli sampling with $n_{\rm base}=1024$
($n_{\rm calls}=4096$ FD solves at $N=20$). For this decomposition both inputs
are treated probabilistically: $E \sim \mathcal{N}(\mu_E,\sigma_E)$ and $q_0 \sim
U(400,600)$~lb/ft. This is intentionally distinct from the p-box framing of
Sections~\ref{sec:nested}--\ref{sec:total}, where $q_0$ remains epistemic to
bound the predictive CDF; Sobol re-casts $q_0$ probabilistically to rank input
contributions to total variance.

% Table + figure: S_1 and S_T per input
% First-order indices sum to 1 - interaction effect; sum check shown in caption.
```

### Build sequence

1. Track A prose edits (parallel-safe, ~2 hrs total).
2. Track B Python additions (~1 hr coding).
3. `cd backend/app/core/structural && python project_prediction_uq.py` (re-runs
   nested sampling + new Sobol stage; ~5 min).
4. Verify `project_figures/fig5_sobol.{pdf,png}` generated.
5. Track B `.tex` edits (~30 min) wiring the new section + figure.
6. `cd .../project_report && pdflatex VVSC_Cusati_Chuang_Project.tex` (twice for refs).
7. Spot-check page count, references resolve, no over/underfull boxes for the new section.
8. Sync the renamed/updated PDF to `construction-ai-proposal/` and update its
   CI workflow + index.html (mirroring how HW3-5 are published).

## Edge Cases & Error Handling

### EC-1: Sobol S₁ near zero or negative
- **Scenario:** With small n_base (≤256), Saltelli S₁ estimators can be slightly
  negative due to Monte Carlo noise even for non-zero true sensitivity.
- **Behavior:** Use n_base = 1024 (4,096 total calls). At this scale, |S₁| > 0.01
  is robust. Caption the figure with `n_calls` so the reader can judge.
- **Test:** Run with n_base ∈ {256, 512, 1024, 2048} and check that S₁ values
  stabilize to within ±0.02 by n_base=1024.

### EC-2: Sum check S₁ + S₁(other) ≠ 1 - interaction
- **Scenario:** For a system with `w_max ∝ q₀ / E`, interaction (S_T - S₁) is
  small but non-zero. Sum of S₁ may be slightly < 1.
- **Behavior:** Expected. Annotate the figure with "Σ S₁ = X.XX (interaction =
  Y.YY)" so the reader sees the bookkeeping is honest.
- **Test:** Verify Σ S_T > Σ S₁ (always true theoretically) and both are within
  numerical tolerance of unity for an additive-dominant model.

### EC-3: Page count overflow
- **Scenario:** Adding §7.2 sensitivity (text + table + figure) pushes the
  conference-paper format over 12-13 pages.
- **Behavior:** Conference-paper format has no hard page limit (it's not a
  course-imposed cap; HW reports were 9 pages each). Acceptable to grow to
  13-14 pages.
- **Test:** `pdfinfo VVSC_Cusati_Chuang_Project.pdf | grep Pages` after build.

### EC-4: PDF rebuild misses reference
- **Scenario:** New `\label{sec:sensitivity}` cross-referenced before defined,
  causes "??" in the PDF.
- **Behavior:** Run `pdflatex` twice as already in `Makefile`.
- **Test:** `grep -c "??"` on the compiled `.log` is zero.

### EC-5: Re-run determinism
- **Scenario:** Random sampling produces different Sobol values each run.
- **Behavior:** Both `qmc.Sobol(seed=42)` and `np.random.default_rng(42)` are
  used — outputs are deterministic across runs on the same machine.
- **Test:** Run twice; assert identical S₁/S_T values to 12 decimals.

## Acceptance Criteria

### AC-1: Sensitivity analysis section present
- **Given** the rebuilt PDF
- **When** searching the table of contents
- **Then** §7.2 (or equivalent placement) titled "Sensitivity Analysis" exists,
  contains Sobol S₁ and S_T values for E and q₀, and references one new figure.

### AC-2: Sobol figure exists and resolves
- **Given** the build artifacts
- **When** opening `project_figures/fig5_sobol.pdf`
- **Then** a side-by-side bar chart of S₁ and S_T for {E, q₀} renders, with
  caption listing `n_calls = 4096`.

### AC-3: Reconciliation paragraph addresses HW2 promises
- **Given** the rebuilt PDF
- **When** reading §7 Discussion
- **Then** there is at least one paragraph that explicitly names: (i) IRC R602.7
  prescriptive comparison, (ii) L/240 vs L/360 serviceability limits, (iii) σ_max
  sanity check against NDS-2018 grade-1 LVL Fb allowable.

### AC-4: Linearity assumption justified
- **Given** the rebuilt PDF §6.4
- **When** reading the d⁺(q₀), d⁻(q₀) regression equations
- **Then** the surrounding prose cites the q₀-linearity of the EB exact solution
  (eq. 2) as physical motivation for the linear regression form.

### AC-5: All file/cite consistency fixes applied
- **Given** the source tree
- **When** running `ls .../project_report/`
- **Then** `VVSC_Cusati_Chuang_Project.tex` exists (renamed from `_Chuang_ChengShun_`),
  and the proposal repo CI workflow + index.html reference the new name.

### AC-6: PDF builds clean
- **Given** `cd .../project_report && pdflatex VVSC_Cusati_Chuang_Project.tex` (twice)
- **When** the second pass completes
- **Then** exit code is 0, the `.log` file contains zero `\\ref{??}` errors, and
  `pdfinfo` reports a positive integer page count ≤14.

### AC-7: Re-runnable
- **Given** a clean checkout
- **When** running `python project_prediction_uq.py`
- **Then** the script completes without error and emits all 5 figures
  (`fig1_pbox.pdf`, `fig2_pbox_vs_uniform.pdf`, `fig3_model_form_extrap.pdf`,
  `fig4_total_uncertainty.pdf`, `fig5_sobol.pdf`).

### AC-8: Pre-submission rehearsal (per RD-9)
- **Given** a compiled PDF that satisfies AC-1 through AC-7
- **When** the time is at most 2026-05-06 10:00 EST (T-12h before deadline)
- **Then** the PDF has been uploaded to Canvas as a draft submission, and
  the user has confirmed (i) Canvas accepted the filename, (ii) Canvas
  server timestamp is consistent with local upload time, (iii) file size
  matches byte-for-byte, (iv) the draft is visible under the correct
  assignment slot.

### AC-9: Numerical-consistency reconciliation file (per RD-6)
- **Given** the source tree pre-submission
- **When** opening `construction/design/final-report-numeric-reconciliation.md`
- **Then** every quantity appearing in two or more locations has a row
  marked "Reconciled? ✓" with matching values.

### AC-10: Determinism snapshot (per RD-5)
- **Given** the source tree
- **When** running `python project_prediction_uq.py` twice in succession
- **Then** both runs produce identical numerical output (asserted against
  `project_results_snapshot.json` to 1e-5 absolute tolerance).

## Technical Notes

- **Affected components:**
  - `backend/app/core/structural/project_prediction_uq.py` (add ~80 lines)
  - `backend/app/core/structural/project_report/VVSC_Chuang_ChengShun_Project.tex` (rename + ~15 prose edits)
  - `backend/app/core/structural/project_figures/fig5_sobol.{pdf,png}` (new artifact)
  - `construction-ai-proposal/.github/workflows/build-and-publish-pdf.yml`
    (rename target file, add fig5 if mirroring) — secondary, only after the
    construction-ai branch is merged into the proposal-repo PDF pipeline.
- **Patterns to follow:**
  - Existing `print_pbox_table()`, `fig1_pbox()` style for `print_sobol_table()`,
    `fig5_sobol_indices()` (reuse `_save` helper, matplotlib styling).
  - Existing section-then-figure-then-table prose pattern.
- **Data model changes:** None.
- **Determinism:** `seed=42` everywhere, matching existing convention.
- **Numerical references to be added:**
  - Saltelli, A. (2010). "Variance based sensitivity analysis of model output."
    *Computer Physics Communications* 181(2): 259-270. — for the S₁/S_T estimators.
  - Iooss, B. & Lemaître, P. (2015). "A Review on Global Sensitivity Analysis
    Methods." — for general framing.

## Dependencies

- `scipy.stats.qmc` (already used in repo via `scipy` requirement) — Sobol QMC
  sampler. Available in scipy ≥ 1.7.
- No new third-party packages required.

## Review Decisions (Phase 7-8)

- **RD-1 (Tech Lead #1, q₀ probabilistic recast):** The Sobol section will
  *lean into the duality* with a 3-4-sentence framing paragraph citing
  Roy 2011 §2-3, explicitly stating that variance-based decomposition
  requires reversibly recasting epistemic q₀ as probabilistic for the
  decomposition only, and that the p-box prediction representation
  (Sections 6.2-6.5) is unchanged.

- **RD-2 (QA #1a, fig5 sanity bounds):** `run_sobol_indices()` will assert
  `0.05 ≤ S_T[i] ≤ 0.95` for each input and raise a `RuntimeError` with a
  clear message if exceeded. The arithmetic-not-rendering check protects
  against a 1am pre-submission rebuild that produces a numerically-correct-but-
  visually-broken figure. Manual visual confirmation of fig5 remains a
  separate AC (AC-2 unchanged).

- **RD-3 (QA #1b + Tech Lead #2, §6.4 circularity, FINAL):** **Option (b) —
  keep the regression and existing numerical values, rewrite §6.4 prose to
  defuse circularity through transparency.** Rationale: linear-scaling
  point estimates differ from the reported 95% PI values by 4% (d⁺) and 1%
  (d⁻); these deltas are below the headline-precision of Table 4's
  Total upper/lower (~33%) and the Abstract's "32%". Re-deriving everything
  invites typo-cascade across Table 4, fig3, fig4, abstract, and conclusions
  three days from deadline. Re-framing the regression as recovering the
  correct physical slope (per EB exact solution eq. 2 q₀-linearity) with
  the PI as a *conservative bound on the extrapolation procedure* (not a
  measurement-noise estimate) is honest, defensible, and limited to one
  section. Specific §6.4 prose additions:
  1. Note explicitly that the five hypothetical validation points were
     anchored on the validated d⁺(500), d⁻(500) and assumed proportional
     to q₀.
  2. Justify the proportionality: under the EB exact solution (eq. 2),
     w_max is exactly linear in q₀ for fixed E; therefore d⁺(q₀), d⁻(q₀)
     inherit the same q₀-linearity from the simulation outputs they
     measure against.
  3. Frame the 95% PI as a conservative bound on the extrapolation
     procedure (the choice to fit 5 fabricated points), not a
     measurement-noise estimate.
  4. Sanity-check under strict point-scaling: U_MF⁺(600) = 1.2 · d⁺(500) =
     1.93×10⁻³ in (4% below the regression PI of 2.003×10⁻³ in adopted
     for the report); U_MF⁻(600) = 1.2 · d⁻(500) = 0.636×10⁻³ in (1%
     below 0.642×10⁻³ in). Adopting the PI values yields the conservative
     side of this small ambiguity.
  No re-run, no Table 4 edits, no fig3/4 edits, no abstract or conclusions
  edits. Effort: 30-45 min prose only.

- **RD-5 (QA #2a, determinism guard):** Add a regression-snapshot check to
  `project_prediction_uq.py`. After running the full pipeline, write a
  `project_results_snapshot.json` containing key invariants to 6 decimal
  places: p-box 5/50/95-pct bounds at each Nₑ, U_MF⁺/U_MF⁻, AVM/MAVM at
  validation q₀=500, Sobol S₁/S_T per input, total upper/lower percentages.
  On subsequent runs, compare against the committed snapshot; raise
  `RuntimeError` on any field diverging by > 1e-5 absolute (catches RNG
  ordering changes from the new Sobol code-path). Commit the snapshot
  alongside the code. Effort: ~30 min including assertion logic.

- **RD-6 (QA #2b, cross-document numerical reconciliation):** Before
  submission, do a manual diff of every numerical claim that appears in
  two or more locations. Concretely produce (and commit) a small file
  `construction/design/final-report-numeric-reconciliation.md` listing:
  | Quantity | Abstract | Conclusions | Table N | Other locations | Reconciled? |
  Cover at minimum:
  - Total upper / total lower percentages (Abstract → Conclusions item 5 → Table 4)
  - p-box 5th/95th pct at q₀=600 (Abstract → Table 1 row Nₑ=25 → IRC paragraph)
  - U_NUM at N=20 (Abstract → §4.2 → Table 6 / App. A)
  - p_obs (Abstract → §3 → Table A.x)
  - σ_max sanity (G2 IRC paragraph → §2 governing-eq paragraph)
  - **memory-bank/activeContext.md** Final Project Key Facts block —
    treat as internal only but reconcile on the same pass to avoid future
    drift.
  Sign-off: this file is updated and "all green" before the final PDF is
  built and submitted.

- **RD-7 (Tech Lead #3, submission/publication path):** **Hybrid (option c).**
  Pre-deadline: submit local PDF to Canvas only. Do NOT touch
  `construction-ai-proposal` CI in the pre-deadline window. Post-deadline:
  copy `.tex` + project_figures into
  `construction-ai-proposal/CS6444/Project/` mirroring HW3-5; add a
  Compile CS6444 Project step to `.github/workflows/build-and-publish-pdf.yml`;
  add an entry to `public/index.html`; push; verify the GitHub Action
  publishes the PDF; copy the live URL into a follow-up commit on
  `Final-report-of-VVUQ` for posterity. Rationale: avoids the worst
  failure mode (CI breaks at 21:00 May 6 blocking submission); preserves
  HW2-5 pattern consistency as an archive deliverable rather than a
  hot-path dependency.

- **RD-8 (Tech Lead #3, branch strategy):** **Tag at submission, merge
  after.** Sequence:
  1. Pre-deadline work commits land on `Final-report-of-VVUQ`.
  2. Final compile passes all ACs → `git tag final-project-submitted-2026-05-06`
     at the exact submitted commit. Push tag to origin.
  3. Submit PDF to Canvas.
  4. Wait for Canvas confirmation + screenshot timestamp.
  5. **Post-submission:** open PR `Final-report-of-VVUQ` → `master`,
     merge after review.
  6. Post-deadline mirror to `construction-ai-proposal` per RD-7.
  Rationale: tag captures immutable submission state; no pre-deadline
  merge-conflict risk; master eventually reflects canonical history;
  branch + tag preserve the submission snapshot regardless of subsequent
  evolution.

- **RD-9 (QA #3, pre-submission rehearsal):** **Add pre-submission rehearsal
  to acceptance criteria** (option a). Upload the compiled PDF to Canvas as
  a *draft submission* by 2026-05-06 10:00 EST (12 hours before the 22:00
  EST cliff). Verify: (i) Canvas accepts the filename without rejection,
  (ii) Canvas reports a server-side timestamp consistent with the local
  upload time (catches time-zone confusion), (iii) the uploaded file size
  matches the local file size byte-for-byte, (iv) the draft is visible in
  Canvas under the correct assignment. Replace with the final-final upload
  closer to deadline if any post-rehearsal edits land. Belt-and-suspenders
  against last-hour failure modes.

- **RD-4 (numerical-claim hygiene, surfaced 2026-05-03):** During Phase 5
  sample-implementation drafting, an arithmetic error appeared in a stated
  σ_max sanity-check value (487.6 psi). Recomputed:
  M_max(q₀=600 lb/ft) = q₀ L² / 8 = 50 · 96² / 8 = **57,600 lb·in**;
  S = bd²/6 = 3.5 · 11.25² / 6 = **73.83 in³**;
  σ_max = M/S = 57,600 / 73.83 = **780.2 psi** (still well under NDS-2018
  Grade-1 LVL Fb ≈ 2,400 psi). G2 paragraph copy must use 780.2 psi, not
  487.6. Lesson: every numerical claim added during Track A prose edits
  must be recomputed independently before draft, not copied from spec
  prose blindly.

## Open Questions

- **OQ-1 (deferred to implementation):** Should the Sobol section include a
  Morris screening *as well* (cheap, ~30 base trajectories, useful for showing
  that the screening picks the same dominant input as the variance-based
  decomposition)? Default: no — Sobol alone is sufficient for d=2; only add
  Morris if section ends up looking thin.
- **OQ-2 (deferred to implementation):** Should fig5 also include a scatter
  plot of `(E, q₀, w_max)` to visualize the response surface? Default: no —
  one figure per analysis is the established pattern in the report.
- **OQ-3 (administrative):** When merging back to master, should the file
  rename `git mv` happen on `Final-report-of-VVUQ` or on master? Default:
  on `Final-report-of-VVUQ` (closer to source of truth for the report).
