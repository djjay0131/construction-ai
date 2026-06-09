# Sprint 1b: VVUQ Presentation Slides (Structural Hypothesis Evaluation)

**Status:** IMPLEMENTED
**Date:** 2026-06-08
**Implemented:** 2026-06-08
**Author:** Jason Cusati (with AI assistance)
**Sprint:** 1b of 1 (VVUQ Phase 3 closeout)
**Roadmap source:** `construction-ai-proposal/construction/design/2026-product-roadmap.md`

## Problem

The Beamer presentation (`construction-ai-proposal/proposal/presentation.tex`,
currently 21 slides) was authored before the VVUQ integration. The IEEE paper
has been augmented with §5a (Verification, Validation, and Uncertainty
Quantification), a Phase 3.5 (Structural Hypothesis Evaluation) in the
architecture, and a 6th Structural Hypothesis Agent in the agentic workflow —
but none of this physics-and-V&V story is told in the slide deck. A reviewer
or audience looking at the deck would have no awareness of the proposal's
scientific computing contribution.

Sprint 1 of the roadmap explicitly calls for "4 new presentation slides
(Structural Challenge, Hypothesis Generation, PDE Evaluation, V&V)".

## Goals

- Add a new `\section{Structural Hypothesis Evaluation}` to
  `proposal/presentation.tex` containing 4 new frames, in the order:
  1. **Structural Challenge** — frame the problem of inferring load paths from
     architectural plans
  2. **Hypothesis Generation** — enumerate plausible load-path configurations
  3. **PDE Evaluation** — apply the Euler–Bernoulli beam solver to each
     hypothesis
  4. **V&V** — verification, validation, UQ framework
- Place the new section between `\section{Agentic Workflow}` and
  `\section{Technology Stack}` — the natural narrative point where the physics
  layer becomes relevant after introducing the agent that uses it.
- Each frame:
  - Uses the existing VT Madrid/circles theme (vtmaroon / vtorange / vtgray colors)
  - 3–5 concise bullets OR a small block/tikz diagram, in line with the deck's
    existing slide density
  - Frametitle exactly matching the planned name above
- Total deck grows from 21 → 25 slides
- Compile clean to a publishable PDF
- Pages mirror (`presentation.pdf`) updated on push to master

## Non-Goals

- Editing existing 21 slides for tone, content, or formatting (don't churn what
  works)
- Adding `\cite{}` calls in slides (presentations don't show full citations; the
  paper already cites; Sprint 1a covered that)
- Changing the Agenda slide to mention the new section
  (low-value churn; the section header gives it visibility)
- Adding new packages or themes
- Updating `main.pdf` — that's the IEEE paper, separate artifact

## User Stories

- As a reviewer scanning the slide deck for the first time, I want to see the
  structural / V&V story so I know the proposal has scientific rigor.
- As Jason presenting later, I want a clear flow from "structural challenge" →
  "we generate hypotheses" → "we evaluate via PDE" → "we verify and validate it"
  that audiences can follow in 3–4 minutes.

## Design Approach

### Insertion point in `presentation.tex`

Currently the file has the following section sequence (frame line numbers shown):
- Title (55) → Agenda (62) → Problem (69, 71, 92) → Our Solution (116, 118, 145)
  → Agentic Workflow (170, 172, 198) → **[INSERT HERE]** → Technology Stack
  (221) → ... → Conclusion → Backup

The new `\section{Structural Hypothesis Evaluation}` goes between line 218
(closing of Agentic Workflow's last frame) and line 221 (`\section{Technology
Stack}`). I'll find the closing `\end{frame}` right before line 221 and insert
the new section + 4 frames immediately after it.

### Slide content (target 3–5 bullets per frame)

**Frame 1: Structural Challenge**

The framing problem: floor plans show walls and openings but don't reveal load
paths. Builders must infer which walls bear load, where headers are required,
and what tributary areas apply. Bullets:
- Architectural plans show geometry, not structural intent
- Builders manually infer load paths (error-prone, time-consuming)
- 10–15% header sizing errors observed in field studies
- No commercial takeoff tool validates structural plausibility
- Goal: physics-based reasoning over inferred structural hypotheses

**Frame 2: Hypothesis Generation**

Multiple plausible load paths exist for each plan; the system enumerates them
and represents each as a Knowledge-Graph subgraph. Bullets / block:
- Each hypothesis = a candidate (load-bearing-wall set, tributary partition)
- Generated from architectural geometry + IRC framing heuristics
- Stored as KG nodes (StructuralHypothesis, LoadPath, BeamEvaluation)
- Top 2–3 ranked by cost, robustness, design flexibility
- Tradeoff narrative auto-generated for the user

**Frame 3: PDE Evaluation**

The Euler–Bernoulli beam PDE applied to each candidate header / beam. Bullets:
- Per hypothesis: solve $EI \, w''''(x) = q(x)$ on each candidate beam
- Finite-difference solver, ghost-point near-boundary stencils (verified to 2nd order)
- Boundary conditions per actual end-fixity (simply-supported / clamped)
- Computes $w_{\max}$, $M_{\max}$, $\sigma_{\max}$, $\tau_{\max}$
- Pareto-filters against $F_b$, $F_v$, deflection limits

**Frame 4: V&V**

Three pillars: verification (code correctness), validation (physical
correctness), UQ (uncertainty propagation). Bullets / block:
- **Verification:** grid convergence (observed $p \approx 2$, GCI per Celik 2008)
- **Validation:** IRC span tables + 20–30 stamped-design dataset
- **UQ:** Monte Carlo + LHS over $(W, q_\text{roof}, q_\text{floor}, E)$
- Robust feasibility: assemblies accepted only if $P_\text{fail} < 0.01$
- Cross-references the IEEE paper's Section 5a

### Frame style template

Match the existing deck's style:

```latex
\begin{frame}{Frame Title}
\begin{itemize}
  \item Bullet 1
  \item Bullet 2
  \item Bullet 3
\end{itemize}
\end{frame}
```

For frames that benefit from a TikZ diagram or a block, use the deck's existing
block conventions (e.g., the `\begin{block}{...}` pattern visible in existing
Architecture slides).

## Sample Implementation

```latex
% =============================================================================
% STRUCTURAL HYPOTHESIS EVALUATION (VVUQ — NEW)
% =============================================================================
\section{Structural Hypothesis Evaluation}

\begin{frame}{Structural Challenge}
\begin{itemize}
  \item Architectural plans show \textbf{geometry}, not structural intent
  \item Builders manually infer load paths — error-prone, time-consuming
  \item Field studies report \textbf{10--15\% header sizing errors}
  \item No commercial takeoff tool validates structural plausibility
  \item \textbf{Goal:} physics-based reasoning over inferred structural hypotheses
\end{itemize}
\end{frame}

\begin{frame}{Hypothesis Generation}
\begin{itemize}
  \item Each \textbf{hypothesis} = candidate (load-bearing-wall set, tributary partition)
  \item Generated from architectural geometry + IRC framing heuristics
  \item Stored in KG: \texttt{StructuralHypothesis}, \texttt{LoadPath}, \texttt{BeamEvaluation}
  \item Top 2--3 ranked by cost, robustness, design flexibility
  \item Tradeoff narrative auto-generated for the user
\end{itemize}
\end{frame}

\begin{frame}{PDE Evaluation}
\begin{itemize}
  \item Per hypothesis: solve $EI\,w''''(x) = q(x)$ on each candidate beam
  \item Finite-difference solver, ghost-point near-boundary stencils
  \item Verified 2\textsuperscript{nd}-order accurate ($p_\text{obs} \approx 2.00$)
  \item Computes $w_{\max}$, $M_{\max}$, $\sigma_{\max}$, $\tau_{\max}$
  \item Pareto-filters against $F_b$, $F_v$, deflection limits
\end{itemize}
\end{frame}

\begin{frame}{Verification, Validation, and Uncertainty Quantification}
\begin{itemize}
  \item \textbf{Verification:} grid convergence, observed $p \approx 2$, GCI framework
  \item \textbf{Validation:} IRC span tables + 20--30 stamped-design dataset
  \item \textbf{UQ:} Monte Carlo + Latin Hypercube over $(W, q_\text{roof}, q_\text{floor}, E)$
  \item \textbf{Robust feasibility:} accept only if $P_\text{fail} < 0.01$
  \item Full V\&V framework detailed in IEEE paper §5a
\end{itemize}
\end{frame}
```

## Edge Cases & Error Handling

### Insertion point mis-identified
- **Scenario:** The implementer can't find the exact line between Agentic Workflow
  closing and Technology Stack opening.
- **Behavior:** Use a unique anchor string from the file (e.g., the `\section{Technology Stack}`
  line itself) and insert immediately before it. Verify visually after.
- **Test:** After insert, grep that `Structural Hypothesis Evaluation` appears
  BEFORE `Technology Stack` in the file.

### Beamer compile error from frametitle special chars
- **Scenario:** The V&V frame title uses `&` in plain text — Beamer needs `\&`.
- **Behavior:** Use the full title "Verification, Validation, and Uncertainty
  Quantification" instead of "V&V" to dodge the issue entirely; or escape if
  the short form is needed.
- **Test:** `make presentation.pdf` compiles clean.

### TikZ / mathmode issues in bullets
- **Scenario:** Math expressions like `EI w''''(x) = q(x)` need `$...$`.
- **Behavior:** Already in sample. Implementer verifies on compile.
- **Test:** Compile log shows zero `Undefined control sequence` or `Missing $`.

### Total slide count doesn't reach 25
- **Scenario:** Implementer accidentally drops a frame or the count miscounts.
- **Behavior:** `pdfinfo presentation.pdf | grep Pages` must show 25.
- **Test:** AC-5 below.

### Slide overflow on text-heavy frames
- **Scenario:** 5 bullets + math expressions don't fit on 16:9 Madrid theme.
- **Behavior:** Trim to 3–4 bullets or use `\small` text. Visual sanity check
  the PDF.
- **Test:** Implementer opens `presentation.pdf` and confirms no overflow on
  any new frame (visual; not automatable).

## Acceptance Criteria

### AC-1: New section header present
- **Given** the implementation is complete
- **When** `grep -c "^\\\\section{Structural Hypothesis Evaluation}" proposal/presentation.tex` is run
- **Then** the count is exactly 1

### AC-2: All 4 frame titles present
- **Given** the implementation is complete
- **When** each frametitle is grepped
- **Then**
  - `\frametitle{Structural Challenge}` OR `\begin{frame}{Structural Challenge}` returns 1
  - `Hypothesis Generation` returns 1
  - `PDE Evaluation` returns 1
  - `Verification, Validation, and Uncertainty Quantification` OR `V\&V` frametitle returns 1

### AC-3: New section precedes Technology Stack
- **Given** the implementation is complete
- **When** the line numbers of `\section{Structural Hypothesis Evaluation}` and
  `\section{Technology Stack}` are compared
- **Then** the Structural section line number is less than the Technology Stack
  line number

### AC-4: Compile clean
- **Given** the implementation is complete
- **When** `cd proposal && make presentation.pdf` is run (or `pdflatex presentation`)
- **Then** exit code is 0
- **And** `Undefined control sequence` count in the log is 0
- **And** `Missing $` count is 0

### AC-5: Slide count is exactly 25
- **Given** `presentation.pdf` is freshly compiled
- **When** `pdfinfo presentation.pdf | grep Pages` is run
- **Then** the value is 25 (was 21, +4)

### AC-6: Each new frame has non-empty content
- **Given** the implementation is complete
- **When** each `\begin{frame}{<new title>}` ... `\end{frame}` block is read
- **Then** it contains at least 3 `\item` entries OR a block/tikz with content
- **And** no frame is empty placeholder

### AC-7: Existing 21 slides untouched in content
- **Given** the implementation is complete
- **When** `git diff HEAD presentation.tex` is run
- **Then** all changes are additions (lines starting with `+`); zero deletions of
  existing content (lines starting with `-` not in the new block)

### AC-8: VT theme conventions preserved
- **Given** the implementation is complete
- **When** the new frames are visually inspected
- **Then** they use only `\structure`, `\textbf`, `\textit`, default itemize/block
  conventions — no `\color{...}` or custom font commands

### AC-9: Slide titles match the spec exactly
- **Given** the spec lists 4 titles
- **When** the new frames are read
- **Then** the frametitles use the canonical phrasing:
  "Structural Challenge", "Hypothesis Generation", "PDE Evaluation",
  "Verification, Validation, and Uncertainty Quantification" (or "V\&V" — pick one)

### AC-10: Pushed to origin/master
- **Given** the implementation + verify is complete
- **When** `git status -sb` is run in the proposal repo
- **Then** the branch is in sync with origin/master and contains the new commit

## Technical Notes

- **Affected file:** `construction-ai-proposal/proposal/presentation.tex` only
- **Tools:** Edit tool for inserting the new section before
  `\section{Technology Stack}`; do not Write the whole file
- **No changes to:** main.tex, references.bib, any other section .tex, Makefile

## Dependencies

- Proposal repo on master, clean working tree before starting
- Sprint 1a complete (citations in place — informs language used on V&V slide)
- Roadmap doc `construction/design/2026-product-roadmap.md` Sprint 1 describes
  this work

## Open Questions

- Use short title "V&V" or full title "Verification, Validation, and Uncertainty
  Quantification" for frame 4? **Decision:** use the full title — clearer for
  audience scanning the agenda; dodges Beamer `\&` escape issue cleanly.
- Add the new section to the Agenda slide? **Decision:** non-goal per spec
  ("Don't churn what works"). The section header gives visibility via auto-TOC
  if the theme builds one (Madrid does not by default).

## Implementation Log (2026-06-08)

- Inserted new section between Agentic Workflow (line 216 end) and
  Technology Stack (now line 266).
- 4 frames added per sample implementation; each with 5 bullets.
- Used long title "Verification, Validation, and Uncertainty Quantification"
  for frame 4 per spec open-question decision.
- Replaced ASCII hyphen `-` (em-dash candidates) with LaTeX `---` in the
  Structural Challenge bullet "error-prone, time-consuming" for typography.
- Math expressions guarded with `$...$` per the sample (no `Missing $` errors).
- `\&` not needed: dodged by using the long title.
- Compile: `pdflatex` exit 0, 25 pages, 0 errors.
- Out-of-scope discovery: existing frame "5 Specialized Agents" (lines
  198--216) is stale — paper now describes 6 agents (since VVUQ PR #6 added
  the Structural Hypothesis Agent). Sprint 1b non-goal says don't edit
  existing slides; flagged for a follow-up cleanup sprint after VVUQ
  Phase 3 closeout.

| AC | Result |
|---|---|
| AC-1: section header present | ✓ (1 match) |
| AC-2: 4 frametitles present | ✓ (1 match each) |
| AC-3: new section precedes Technology Stack | ✓ (line 221 < 266) |
| AC-4: compile clean | ✓ (exit 0, 0 errors) |
| AC-5: 25 slides | ✓ |
| AC-6: each new frame ≥3 items | ✓ (5 items each) |
| AC-7: zero existing-content deletions | ✓ |
| AC-8: no rogue color/font commands | ✓ (0 matches) |
| AC-9: canonical titles match exactly | ✓ |
| AC-10: pushed to origin | pending (commit follows) |
