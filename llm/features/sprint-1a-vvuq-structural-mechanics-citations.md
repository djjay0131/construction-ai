# Sprint 1a: Structural Mechanics + V&V + UQ Citations for IEEE Proposal

**Status:** IMPLEMENTED
**Date:** 2026-06-08
**Implemented:** 2026-06-08
**Author:** Jason Cusati (with AI assistance)
**Sprint:** 1a of 1 (VVUQ Phase 3 closeout)
**Roadmap source:** `construction-ai-proposal/construction/design/2026-product-roadmap.md`

## Problem

The proposal paper (`construction-ai-proposal/proposal/main.tex`) integrates a VVUQ
framework in Section 5a (`05a-verification-validation.tex`) covering Euler-Bernoulli
beam theory, mesh convergence, Monte Carlo UQ, robust feasibility, and multi-criteria
Pareto ranking. But the section currently contains only ONE citation (`irc2021`).
Every other claim — verification methodology, beam theory, FEM, Monte Carlo, LHS,
reliability — is unsupported. The proposal would not survive peer review in its
current state, and Sprint 1 of the roadmap explicitly calls for 10–15 structural
mechanics citations as part of the VVUQ Phase 3 closeout.

## Goals

- Add 10–15 NEW bibliography entries to `proposal/references.bib` covering the four
  pillars implicit in §5a: V&V methodology, beam/continuum mechanics, FEM,
  uncertainty quantification + sampling, structural reliability.
- Wire those entries into `05a-verification-validation.tex` via `\cite{}` calls at
  the specific claims they support — not just "dump-and-list" at the end.
- Every new entry web-verified (per `feedback_reference_verification.md`): author,
  title, year, venue, page range checked against publisher record. **Zero
  hallucinations.**
- Maintain the existing IEEE bibitem style used in the rest of `references.bib`.
- Paper still compiles clean to ≤14 pages.

## Non-Goals

- Adding citations to other sections (01-motivation, 02-architecture, etc.). Those
  are already cited adequately.
- Reorganizing or renaming any existing bibitem.
- Adding citations the implementer cannot web-verify. Skip a candidate rather than
  fabricate metadata.
- Modifying `main.pdf` directly — only the source files; CI compiles.

## User Stories

- As a reviewer of the IEEE proposal, I want every claim in §5a to be backed by a
  citation so I can trust the technical assertions.
- As Jason (defending the proposal later), I want only verified citations in the
  bibliography so I don't get caught with a hallucinated entry.

## Design Approach

### Topics that need citation support (mapped to §5a claims)

| §5a claim | Topic | Anchor reference (any equivalent OK if verified) |
|---|---|---|
| "verification ensures algorithms correctly solve mathematical models" | V&V methodology | Roy & Oberkampf 2010 OR Roache 1998 |
| Verification + Validation general framework | V&V standards | ASME V&V 10-2006 (solid mechanics) and/or V&V 20-2009 |
| "convergence tests with mesh refinement" + observed order | Code verification, MMS, GCI | Salari & Knupp (MMS) OR Celik et al. 2008 (GCI) |
| "Euler-Bernoulli beam solver verified against closed-form" | Beam theory foundation | Timoshenko & Goodier "Theory of Elasticity" |
| "(finite-difference or finite-element discretization)" | FEM | Reddy "Introduction to FEM" OR Bathe "Finite Element Procedures" |
| "Monte Carlo sampling converges as N → ∞" | Monte Carlo | Robert & Casella 2004 "Monte Carlo Statistical Methods" |
| "Random Variable Specification" (Uniform / Normal distributions) | Probability in engineering | Ang & Tang "Probability Concepts in Engineering" Vol 1 |
| Latin Hypercube Sampling (implicit in MC discussion) | LHS | McKay, Beckman, Conover 1979 |
| "P_fail < 0.01 (1% failure probability threshold)" | Structural reliability | Melchers & Beck "Structural Reliability Analysis and Prediction" |
| "multi-criteria score" / Pareto-optimal | Multi-objective optimization | Deb 2001 OR Miettinen 1999 |
| UQ framework / aleatory + epistemic | UQ handbook | Ghanem, Higdon, Owhadi 2017 |
| (Bonus) Sobol sensitivity if useful in revised text | Sobol indices | Sobol 1993 OR Saltelli et al. 2010 |
| (Bonus) Continuum mechanics foundation | Continuum mechanics | Malvern 1969 OR Holzapfel 2000 |

Target: 10–15 entries added (10 minimum guarantees coverage; allow up to 15 if more
fit naturally).

### Where each new key gets cited

Each new entry must produce at least one `\cite{}` call in
`05a-verification-validation.tex` at the most natural anchor point.

Suggested anchor map (final wording chosen at implement time; minor prose tweaks
allowed to support the cite):

- `\textbf{Verification: Numerical Correctness}` opening → cite V&V methodology
- `\textbf{Beam Solver Convergence}` opening → cite beam theory + FEM
- "$\delta_{\max} = 5wL^4 / 384EI$" → cite beam theory
- "Convergence tests with mesh refinement ensure spatial discretization errors decay at expected rates" → cite GCI / MMS
- `\textbf{Uncertainty Propagation Convergence}` → cite Monte Carlo statistical
  methods reference
- `\textbf{Random Variable Specification}` opening → cite probability in
  engineering / UQ handbook
- "$P_{\text{fail}} < 0.01$" / Robust Feasibility → cite structural reliability
  reference
- `\textbf{Hypothesis Scoring and Selection}` opening → cite multi-objective
  optimization reference
- (If used) sensitivity language → cite Sobol / Saltelli

### Style

Match the existing IEEE bibitem style in `references.bib`. The file uses
BibTeX-style entries (e.g., `@article{...}`, `@book{...}`, `@techreport{...}`)
even though the document uses IEEEtran. New entries follow the same conventions:
keys are lowercase-with-underscores, year-suffixed where useful for disambiguation.

### Web-verification (per `feedback_reference_verification.md`)

For each candidate entry, before adding to `references.bib`:
1. Web search for `<authors> <title fragment> <venue> <year>`.
2. Cross-check: author list (complete), title (exact), year (publication, not
   submission), venue, volume/issue, page range, DOI (if available).
3. Track verification in a temporary scratch table in this spec under
   "Implementation Log" appended at the end. Each entry gets a one-line verification
   summary: `✓ verified — <field that was different from initial guess if any>`.
4. If a candidate cannot be web-verified, SKIP and replace with another equivalent
   on the topic. Do not invent metadata.

## Sample Implementation

```bibtex
% === V&V methodology ===
@book{roy_oberkampf_2010,
  author    = {Oberkampf, William L. and Roy, Christopher J.},
  title     = {Verification and Validation in Scientific Computing},
  publisher = {Cambridge University Press},
  year      = {2010},
  address   = {Cambridge},
  isbn      = {978-0-521-11360-1}
}

@book{roache1998_vv,
  author    = {Roache, Patrick J.},
  title     = {Verification and Validation in Computational Science and Engineering},
  publisher = {Hermosa Publishers},
  year      = {1998},
  address   = {Albuquerque, NM}
}

% === ASME standards ===
@techreport{asme_vv10_2006,
  author      = {{American Society of Mechanical Engineers}},
  title       = {Guide for Verification and Validation in Computational Solid Mechanics},
  institution = {ASME},
  number      = {V\&V 10-2006},
  year        = {2006},
  address     = {New York, NY}
}

% === Beam theory ===
@book{timoshenko_goodier_1970,
  author    = {Timoshenko, Stephen P. and Goodier, James N.},
  title     = {Theory of Elasticity},
  edition   = {3rd},
  publisher = {McGraw-Hill},
  year      = {1970},
  address   = {New York}
}

% (continued for remaining entries during implement…)
```

```latex
% === Example cite-anchor edits in 05a-verification-validation.tex ===
% BEFORE:
%   Verification ensures that the implemented algorithms correctly solve the mathematical models.
% AFTER:
%   Verification ensures that the implemented algorithms correctly solve the mathematical models~\cite{roy_oberkampf_2010,roache1998_vv}.

% BEFORE:
%   For a simply-supported beam with uniform load $w$, the maximum deflection is:
% AFTER:
%   For a simply-supported beam with uniform load $w$, the maximum deflection is given by Euler--Bernoulli theory~\cite{timoshenko_goodier_1970,reddy_fem}:
```

## Edge Cases & Error Handling

### Citation key collision
- **Scenario:** A candidate key (e.g., `timoshenko_goodier_1970`) is already in
  `references.bib`.
- **Behavior:** Search `references.bib` first. If present, reuse the existing key;
  don't duplicate. Update the key only if the existing entry has metadata errors.
- **Test:** After implementation, grep that no key appears in two `@xxx{...}` blocks.

### Web-verification reveals different metadata than initial draft
- **Scenario:** Initial draft says "1969 edition" but publisher record shows 1970.
- **Behavior:** Use the verified metadata. Note the correction in the Implementation
  Log section appended to this spec.
- **Test:** Implementation Log column "year corrected from initial draft" is recorded
  for any such case.

### Compile breaks on first build after adds
- **Scenario:** New bibitem syntax error (missing `}`, bad escape, etc.).
- **Behavior:** Fix the syntax. Don't skip the compile.
- **Test:** `make all` exits 0 inside `proposal/`.

### Page count exceeds 14 after adds
- **Scenario:** New citations expand the bibliography enough to push the paper
  to 15+ pages.
- **Behavior:** Bibliography is typeset in two-column IEEEtran; 10–15 new entries
  add roughly 0.5 column on the last page. Unlikely to push over 14 pages, but
  verify.
- **Test:** `pdfinfo proposal/main.pdf | grep Pages` shows ≤ 14 after compile.

### Cite key not yet defined when first cited
- **Scenario:** Section edit lands before bibitem add — undefined reference.
- **Behavior:** Add bibitem first, then section edit. Two-pass compile picks up
  refs on second pass; LaTeX `[citation undefined]` warning during compile catches
  any miss.
- **Test:** Compile log shows zero `Warning: Citation .* undefined`.

### Web-verification fails for a candidate (no source found)
- **Scenario:** A topic has no clearly authoritative reference Jason can defend.
- **Behavior:** Drop that candidate. Pick a different topic from the table, or
  finish with fewer total adds (still ≥ 10 minimum).
- **Test:** Implementation Log records the dropped candidate.

## Acceptance Criteria

### AC-1: Between 10 and 15 new entries added to references.bib
- **Given** the implementation is complete
- **When** `git diff HEAD~1 proposal/references.bib | grep -c "^+@"` is run
- **Then** the count is in [10, 15]

### AC-2: All new entries appear in at least one \cite{} call in §5a
- **Given** the implementation is complete
- **When** every new key from references.bib is grepped in 05a-verification-validation.tex
- **Then** every key returns at least one match (no orphaned bibitems)

### AC-3: All new \cite{} calls in §5a resolve
- **Given** `cd proposal && make all` is run
- **When** the compile log is inspected
- **Then** zero `Warning: Citation .* undefined` lines for new keys

### AC-4: Every new entry is web-verified
- **Given** the implementation is complete
- **When** the "Implementation Log" section at the bottom of this spec is read
- **Then** every new key has a `✓ verified` line referencing the source consulted
- **And** any corrections from initial draft are recorded

### AC-5: No bibitem key collisions
- **Given** the implementation is complete
- **When** `grep -E "^@[a-z]+\{" proposal/references.bib | sed 's/^@.*{//;s/,.*//' | sort | uniq -d` is run
- **Then** the output is empty (no duplicate keys)

### AC-6: Paper still compiles to ≤ 14 pages
- **Given** the implementation is complete
- **When** `pdfinfo proposal/main.pdf | grep Pages` is run
- **Then** the value is ≤ 14

### AC-7: Section 5a cite anchors are natural
- **Given** the updated §5a
- **When** read top-to-bottom
- **Then** each `\cite{}` follows a claim that genuinely needs support (no
  cite-dumping in unrelated places like the conclusion sentence)

### AC-8: Existing bibitems untouched
- **Given** the diff
- **When** `git diff HEAD~1 proposal/references.bib | grep -c "^-@"` is run
- **Then** the count is 0 (no deletions or modifications to existing entries)

### AC-9: Implementation Log appended to this spec
- **Given** the implementation is complete
- **When** this spec file is opened
- **Then** an `## Implementation Log` section exists at the end with one row per
  added entry

### AC-10: PR pushed to origin/master
- **Given** the implementation + verify is complete
- **When** `git fetch origin && git status -sb` is run in the proposal repo
- **Then** the branch is in sync with origin/master and contains the new commit(s)

## Technical Notes

- **Affected files:**
  - `construction-ai-proposal/proposal/references.bib` — add new bibitems
  - `construction-ai-proposal/proposal/sections/05a-verification-validation.tex`
    — add `\cite{}` calls at anchor points
- **Tools:**
  - Edit tool for surgical adds to both files (no Write)
  - Web search for verification per entry
- **No changes to:** main.tex, other section files, presentation.tex, Makefile

## Dependencies

- Proposal repo on master, clean working tree.
- `construction-ai-proposal/construction/design/2026-product-roadmap.md` Sprint 1
  describes this work.
- The implementer must have web access for verification.

## Open Questions

- Should the implementer touch the §5a claim text itself when wiring citations,
  or only add `\cite{}` without prose changes? **Decision:** minor prose tweaks
  allowed if they make the cite more natural (e.g. "given by Euler-Bernoulli
  theory~\cite{…}"). No structural rewrites.
- Are there preferred editions of classic textbooks (e.g. Timoshenko has 3
  editions)? **Decision:** use whichever the implementer can find a clean
  publisher record for; record the edition in the bibitem.

## Implementation Log (2026-06-08)

All 14 candidate entries web-verified before adding to `references.bib`. Zero
hallucinations encountered. Two metadata corrections vs initial draft are noted
inline below.

| # | Key | Type | Verified author/year | Notes |
|---|---|---|---|---|
| 1 | `oberkampf_roy_2010` | @book | Oberkampf, Roy 2010 | ✓ verified — Oberkampf is FIRST author (corrected from initial draft `roy_oberkampf_2010`); ISBN 978-0-521-11360-1; Cambridge Univ Press |
| 2 | `roache1998_vv` | @book | Roache 1998 | ✓ verified — Hermosa Publishers, Albuquerque NM; ISBN 978-0-913478-08-0 |
| 3 | `asme_vv10_2006` | @techreport | ASME 2006 | ✓ verified — 36 pages; ANSI/ASME V&V 10-2006; ISBN 978-0-7918-3042-0 |
| 4 | `asme_vv20_2009` | @techreport | ASME 2009 | ✓ verified — ANSI/ASME V&V 20-2009; ISBN 978-0-7918-3209-7 |
| 5 | `celik2008_gci` | @article | Celik, Ghia, Roache, Freitas, Coleman, Raad 2008 | ✓ verified — **6 authors confirmed** (not 4 as initial draft); JFE Vol 130 Issue 7 Article 078001; DOI 10.1115/1.2960953 |
| 6 | `timoshenko_goodier_1970` | @book | Timoshenko, Goodier 1970 | ✓ verified — 3rd ed; McGraw-Hill, NY; ISBN 978-0-07-064720-6 |
| 7 | `reddy_fem_2005` | @book | Reddy 2005 | ✓ verified — 3rd ed (year corrected from 2006 to 2005); McGraw-Hill; ISBN 978-0-07-246685-0 |
| 8 | `bathe_fem_1996` | @book | Bathe 1996 | ✓ verified — 1st ed (Prentice Hall, 1996); ISBN 978-0-13-301458-7. 2nd ed self-published 2014 — chose 1st for clean publisher record |
| 9 | `robert_casella_2004` | @book | Robert, Casella 2004 | ✓ verified — 2nd ed; Springer NY; ISBN 978-0-387-21239-5; 645 pp |
| 10 | `mckay1979_lhs` | @article | McKay, Beckman, Conover 1979 | ✓ verified — Technometrics Vol 21 No 2 pp 239–245; DOI 10.2307/1271432 |
| 11 | `ang_tang_2007` | @book | Ang, Tang 2007 | ✓ verified — 2nd ed; Wiley NY; ISBN 978-0-471-72064-5 |
| 12 | `ghanem_uq_handbook_2017` | @book (editor) | Ghanem, Higdon, Owhadi (eds) 2017 | ✓ verified — Springer International, Cham; ISBN 978-3-319-12384-4; DOI 10.1007/978-3-319-12385-1 |
| 13 | `melchers_beck_2018` | @book | Melchers, Beck 2018 | ✓ verified — 3rd ed; Wiley, Hoboken NJ; ISBN 978-1-119-26599-3 |
| 14 | `deb_moo_2001` | @book | Deb 2001 | ✓ verified — Wiley, Chichester UK; ISBN 978-0-471-87339-6; 487 pp |

**Anchor-point map (final, as wired in `05a-verification-validation.tex`):**

- Section opening: `oberkampf_roy_2010,roache1998_vv,asme_vv10_2006`
- "Verification ensures..." (Verification subsec): `oberkampf_roy_2010,asme_vv10_2006`
- "verified against closed-form analytical solutions": `timoshenko_goodier_1970`
- "(finite-difference or finite-element discretization)": `reddy_fem_2005,bathe_fem_1996`
- "Grid Convergence Index framework": `celik2008_gci,asme_vv20_2009`
- "Monte Carlo sampling converges as N → ∞": `robert_casella_2004`
- "Latin Hypercube Sampling" (added phrase): `mckay1979_lhs`
- "probabilistic and uncertainty-quantification frameworks": `ang_tang_2007,ghanem_uq_handbook_2017`
- "structural reliability practice": `melchers_beck_2018`
- "multi-objective optimization principles": `deb_moo_2001`

**Compile results (2026-06-08):**
- `make all` exits 0
- `main.pdf` = 14 pages (≤14 ✓)
- 0 `Warning: Citation .* undefined` lines
- 0 duplicate bibitem keys
- 0 existing entries modified

All 10 ACs satisfied.
