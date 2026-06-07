# Active Context

**Last Updated:** 2026-06-06 (CS6444 submitted; pivoting to product roadmap)

## Current Work Phase

**Pivot from CS6444 (SUBMITTED) to 2026 Product Roadmap execution**

CS6444 V&V semester project SUBMITTED 2026-05-11 at tag
`final-project-submitted-2026-05-11` (master @ 63f3d7a). All HW2–5 + Final
Project complete and live on GitHub Pages. The pre-submission audit-and-enhance
work (`construction/design/final-report-audit-and-enhancement.md`, IMPLEMENTED,
commit 9ca7300) is closed.

**Next:** Execute the 6-sprint product roadmap at
`../construction-ai-proposal/construction/design/2026-product-roadmap.md`
(committed 2026-06-06, proposal-repo commit ae095ae). The roadmap is also
pointed to from `llm/features/ROADMAP.md` (commit 06d7e0e). Sprint 0
(memory-bank refresh, this work) is the active sprint.

**Sprint sequence:**
- Sprint 0 — Memory-bank refresh (both repos) — in-progress
- Sprint 1 — VVUQ Phase 3 closeout (proposal repo)
- Sprint 2 — Neo4j Setup on GCP + CI/CD bootstrap (implements
  `llm/features/neo4j-setup.md`)
- Sprint 3 — Raster/Scanned Drawing Support (implements
  `llm/features/raster-scanned-drawing-support.md`)
- Sprint 4 — OCR Dimension Extraction (implements
  `llm/features/ocr-dimension-extraction.md`)
- Sprint 5 — Phase 1 integration smoke test against 2–3 plan sets

Burst/opportunistic cadence; each sprint is self-contained. GCP-first deploy
(Cloud Run + AuraDB Free). No local docker stack — memory-constrained dev.

## Current State

**VVSC Study Files:**

| File | Assignment | Status |
|------|----|--------|
| `backend/app/core/structural/beam_solver.py` | — | Base solver (float64 dense LU) |
| `backend/app/core/structural/hw3_verification.py` | HW3 | ✅ Complete |
| `backend/app/core/structural/hw4_solution_verification.py` | HW4 | ✅ Complete |
| `backend/app/core/structural/hw4_report/VVSC_Chuang_ChengShun_HW4.tex` | HW4 Report | ✅ Complete (9 pages) |
| `backend/app/core/structural/hw5_validation_metric.py` | HW5 | ✅ Complete |
| `backend/app/core/structural/hw5_report/VVSC_Chuang_ChengShun_HW5.tex` | HW5 Report | ✅ Complete (9 pages) |
| `backend/app/core/structural/project_prediction_uq.py` | Final Project | ✅ Complete (Sobol §7 + RD-5 snapshot, 21 pytest tests) |
| `backend/app/core/structural/project_report/VVSC_Cusati_Chuang_Project.tex` | Final Report | ✅ Complete (13 pages, audit-and-enhanced) |
| `construction/design/final-report-audit-and-enhancement.md` | Audit spec | IMPLEMENTED |
| `construction/design/final-report-numeric-reconciliation.md` | RD-6 reconciliation | RECONCILED |
| `backend/tests/test_project_prediction_uq.py` | RD-2 / RD-5 tests | 21/21 pass |

**Canonical Material (post-2026-05-11 propagation):**
- **Weyerhaeuser 2.0E Microllam LVL (ESR-1387)** —
  E = 2,000,000 psi, F_b = 2,600 psi, F_v = 285 psi
- Pre-2026-05-11 baseline (Douglas-Fir-No.2, E = 1.6M psi) lives only on
  earlier commits and as-submitted HW3-HW5 PDFs prior to this session

**HW5 Key Facts (Microllam 2.0E):**
- SRQ: **w_max** (p_obs ≈ 2.00, asymptotic, U_NUM = 0.302% at N=20)
- Aleatory input: **E ~ N(2,000,000, 200,000²) psi** (CoV = 10%, per
  ASTM D5457 bound enforced via D5456 QC chain on ESR-1387 grade)
- Synthetic datasets (Option #2): α = 0.0505374 in, β = 0.0617680 in,
  β−α = 0.0112305 in
- Sampling: LHS at n=10, 25, 100 (seed=42, `scipy.special.ndtri`)
- Validation metric: MAVM (signed area between CDF and EDF)
- **All MAVM values positive** → simulation under-predicts deflection
- AVM (n=100): Dataset 1 = 6.07×10⁻³ in, Dataset 2 = 3.89×10⁻³ in
- MAVM (n=100): Dataset 1 = 5.83×10⁻³ in, Dataset 2 = 3.74×10⁻³ in
- **n=25 LHS sufficient** — within 1% of n=100 reference
- |MAVM|/AVM ≈ 0.96 at n=100 — almost entirely one-sided
- Figures: fig1_datasets, fig2_cdf_dataset1, fig3_cdf_dataset2, fig4_avm_mavm_bar
- Output dir: `backend/app/core/structural/hw5_figures/`

**Final Project Key Facts (Microllam 2.0E):**
- Application: 8-ft Microllam 2.0E LVL header, q₀ ∈ [400,600] lb/ft
  (epistemic), E ~ N(2.0M, 200K²) psi (aleatory)
- Method: Nested sampling p-box (outer Nₑ=25 epistemic, inner Nₐ=100 LHS aleatory)
- P-box 5th–95th pct at q₀=600: **[0.038, 0.079] in**
- w_nom at q=600: 0.0673 in
- Epistemic (q₀ p-box) = 16.5% of w_nom; Aleatory (E scatter) = 13.8%
- **Total upper = 37.65% of w_nom**; total lower = 30.74% (asymmetric)
- Model form: d⁺=3.81×10⁻³ in (under-predict), d⁻=0.079×10⁻³ in — extrapolated to q₀=600
- U_MF⁺=4.749×10⁻³ in (7.05%), U_MF⁻=0.0957×10⁻³ in (0.14%);
  U_NUM_max=2.081×10⁻⁴ in (0.31%, corner)
- Sobol S_T = [0.449 (E), 0.560 (q₀)]; near-balanced contributions
- Figures: fig1_pbox, fig2_pbox_vs_uniform, fig3_model_form_extrap,
  fig4_total_uncertainty, fig5_sobol
- Output dir: `backend/app/core/structural/project_figures/`
- Report: `project_report/VVSC_Cusati_Chuang_Project.tex` — **13 pages**, clean compile
- Sensitivity Analysis section §7.2 added with Sobol indices (Saltelli design,
  n_calls=4096); ESR-1387 / ASTM D5456+D5457 stitch chain in §5.1; IRC R602.7
  reconciliation paragraph in §7.4 (σ_max=780 psi vs F_b=2,600 psi → ratio 0.30)
- **25 bibliography references all web-verified** as of 2026-05-11
  (zero hallucinations; 3 metadata typos fixed: gilbert2019 pp, musselman2018
  authors/vol/pp, leichsenring2018 issue/pp). Citation graph clean
  (25 cited, 25 defined, 0 undefined, 0 dead).
- **Future Work section** — 7 directions with 13 cited references:
  Timoshenko shear correction, physical ASTM D198 testing, Bayesian calibration of (E, κₛ),
  PCE surrogate (Sobol indices), creep/moisture time-dependence, semi-rigid boundaries,
  reliability index / fragility (AK-MCS, ASTM D5457 β-target), spatially varying E(x)

**Also updated:** `.gitignore` now ignores all model weight formats
(`*.pt`, `*.pth`, `*.ckpt`, `*.safetensors`, `*.bin`, `*.h5`, `*.pkl`, `*.weights`,
`pretrained/`, `datascience/runs/`, `datascience/*.pth`).

## Immediate Next Steps

Sprint 0 (this work) is in-progress. After it completes:

1. **Sprint 1** — VVUQ Phase 3 closeout in proposal repo (4 slides + 10–15
   structural-mechanics citations + final review).
2. **Sprint 2** — Implement `llm/features/neo4j-setup.md` (SPECIFIED, 10 ACs).
   Includes CI/CD bootstrap (item 11.3 in BACKLOG.md) and Terraform extensions
   for Cloud Run + Artifact Registry + Secret Manager. Provision AuraDB Free
   instance (prod + ci-test) before kicking off.
3. **Sprint 3** — Implement `llm/features/raster-scanned-drawing-support.md`.
4. **Sprint 4** — Implement `llm/features/ocr-dimension-extraction.md`.
5. **Sprint 5** — End-to-end integration smoke test against 2–3 plan sets
   (DXF, vector PDF, scanned PDF). Validate proposal §8 Phase 1 success
   criteria (BOM accuracy >90%, KG query <100ms, full provenance).

Source of truth for next work:
`../construction-ai-proposal/construction/design/2026-product-roadmap.md`
(also pointed to from `llm/features/ROADMAP.md`).

## Repository Relationship

| Repository | Purpose | Status |
| ---------- | ------- | ------ |
| construction-ai | Implementation code + VVSC studies | Active |
| construction-ai-proposal | Research proposal + Pages mirror (CS6444/{HW3,HW4,HW5,Project}/) | Active |

**Proposal architecture this repo implements (reference):**

- Knowledge Graph (Neo4j) — Sprint 2
- Multi-agent workflow — Phase 2 (future, after roadmap Phase 1 completes)
- Cut optimization with OR-Tools — Phase 2 (future)
- Code compliance checking — Phase 3 (future)

## Key Decisions

### Decision: Sync with Proposal Repository

- **Date:** 2026-02-03
- **Decision:** Keep implementation repo synchronized with proposal documentation
- **Rationale:** Single source of truth for architecture, consistent documentation
- **Impact:** Shared memory-bank and construction folder patterns

### Decision: KG-Centered Architecture

- **Date:** 2026-01-16 (from proposal)
- **Decision:** Use Neo4j Knowledge Graph as central data store
- **Rationale:** Externalized, auditable knowledge; provenance tracking
- **Impact:** All agents query/write to KG; deterministic optimization separate from LLM reasoning

## Key Patterns

### Development Patterns

- Follow proposal architecture
- Maintain sync with proposal repo
- Use construction folder for sprint planning
- Keep memory-bank updated

### Documentation Patterns

- Markdown for all documentation
- Update activeContext.md after significant changes
- Reference proposal for design decisions

## Reference Materials

- **Proposal Repo:** `../construction-ai-proposal/`
- **Published Proposal:** [GitHub Pages](https://djjay0131.github.io/construction-ai-proposal/)
- **Architecture:** `../construction-ai-proposal/proposal/sections/02-architecture.tex`
- **VVUQ Plan:** `../construction-ai-proposal/construction/design/vvuq-integration-plan.md`

## Notes for Next Session

- Read ALL memory-bank files on context reset
- Check proposal repo for latest architecture updates
- Review existing backend/frontend code
- Plan implementation sprints based on proposal phases
