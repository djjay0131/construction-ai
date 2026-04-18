# Active Context

**Last Updated:** 2026-04-18 (HW5 complete)

## Current Work Phase

**VVSC Homework Studies — AOE/CS/ME 6444, Spring 2026, Dr. Chris Roy**

Active development of verification and validation scripts for the
Euler-Bernoulli FD beam solver (residential wood header use case).

## Current State

**VVSC Study Files:**

| File | HW | Status |
|------|----|--------|
| `backend/app/core/structural/beam_solver.py` | — | Base solver (float64 dense LU) |
| `backend/app/core/structural/hw3_verification.py` | HW3 | ✅ Complete |
| `backend/app/core/structural/hw4_solution_verification.py` | HW4 | ✅ Complete |
| `backend/app/core/structural/hw4_report/VVSC_Chuang_ChengShun_HW4.tex` | HW4 Report | ✅ Complete (9 pages) |
| `backend/app/core/structural/hw5_validation_metric.py` | HW5 | ✅ Complete |
| `backend/app/core/structural/hw5_report/VVSC_Chuang_ChengShun_HW5.tex` | HW5 Report | ✅ Complete (9 pages) |

**HW5 Key Facts:**
- SRQ: **w_max** (same as HW4 — p_obs ≈ 2.00, asymptotic, U_NUM = 0.063% at N=20)
- Aleatory input: **E ~ N(1,600,000, 160,000²) psi** (CoV = 10%, LVL variability)
- Synthetic datasets (Option #2): α = 0.0631718 in, β = 0.0772100 in, Δ = 0.01404 in
- Sampling: LHS at n=10, 25, 100 (seed=42, `scipy.special.ndtri`)
- Validation metric: MAVM (signed area between CDF and EDF)
- **All MAVM values positive** → simulation under-predicts deflection (unconservative)
- AVM (n=100): Dataset 1 = 7.59×10⁻³ in, Dataset 2 = 4.87×10⁻³ in
- MAVM (n=100): Dataset 1 = 7.29×10⁻³ in, Dataset 2 = 4.67×10⁻³ in
- **n=25 LHS sufficient** — within 1% of n=100 reference
- Figures: fig1_datasets, fig2_cdf_dataset1, fig3_cdf_dataset2, fig4_avm_mavm_bar
- Output dir: `backend/app/core/structural/hw5_figures/`

**Also updated:** `.gitignore` now ignores all model weight formats
(`*.pt`, `*.pth`, `*.ckpt`, `*.safetensors`, `*.bin`, `*.h5`, `*.pkl`, `*.weights`,
`pretrained/`, `datascience/runs/`, `datascience/*.pth`).

## Immediate Next Steps

1. **HW5 due Monday April 27, 2026** — submit `VVSC_Chuang_ChengShun_HW5.pdf`
2. Implementation sprint review (Construction.AI backend/frontend)
- Script: `hw4_solution_verification.py` ✅
- Report: `hw4_report/VVSC_Chuang_ChengShun_HW4.pdf` ✅ (9 pp, inline figs, formal p_th derivation)

## Repository Relationship

| Repository | Purpose | Status |
| ---------- | ------- | ------ |
| construction-ai | Implementation code + VVSC studies | Active |
| construction-ai-proposal | Research proposal | VVUQ integration ongoing |

2. Map current implementation to proposal architecture
3. Identify implementation gaps
4. Create implementation sprint plan

**From Proposal (reference):**

- Knowledge Graph schema (Neo4j)
- Agent workflow implementation
- Cut optimization with OR-Tools
- Code compliance checking

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
