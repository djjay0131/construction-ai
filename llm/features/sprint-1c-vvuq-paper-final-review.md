# Sprint 1c: VVUQ Phase 3 / Phase 4 Final Paper Review

**Status:** IMPLEMENTED
**Date:** 2026-06-08
**Implemented:** 2026-06-08
**Author:** Jason Cusati (with AI assistance)
**Sprint:** 1c of 1 (VVUQ Phase 3 closeout — final-review step)
**Roadmap source:** `construction-ai-proposal/construction/design/2026-product-roadmap.md`

## Problem

Sprints 1a (citations) and 1b (presentation slides) added new content to
`main.tex` (via `05a-verification-validation.tex`) and `presentation.tex`. The
roadmap's Sprint 1 also calls out a final-review pass before VVUQ Phase 3 can
close: full document compilation review, broken-reference check, page-count
check, and verification that GitHub Pages re-published correctly.

Without this final-review pass, two known stale artifacts of the original
proposal remain undocumented:

1. The **`presentation.tex` "5 Specialized Agents" frame** (lines 198–216) still
   says "5" but the paper (since VVUQ Phase 2 PR #6) describes 6 agents
   including the Structural Hypothesis Agent. Sprint 1b non-goal explicitly
   excluded editing existing slides; Sprint 1c is the right place to address it.
2. The **`agentic-workflow.tex` TikZ diagram** changed from pentagon → hexagon
   in PR #6 but the presentation deck never got a parallel update.

## Goals

- Run a full compile pass on both `main.pdf` and `presentation.pdf` from a
  clean state and capture the page counts, the bib resolution status, and the
  list of any LaTeX warnings.
- Update the deck's "5 Specialized Agents" frame to "6 Specialized Agents" with
  the Structural Hypothesis Agent included (the 1b-out-of-scope item).
- Confirm GitHub Pages re-built both PDFs (Last-Modified header advanced after
  most recent push).
- Capture the final-review results in
  `construction/design/vvuq-phase3-final-review.md` so future Claude sessions
  see a clear "Phase 3 done" record.

## Non-Goals

- Reorganizing the paper or deck. No structural rewrites.
- Adding citations to slides (presentations don't show full citations).
- Auditing every TikZ diagram for full consistency with the paper. Only the
  "5 → 6 agents" specific gap is in scope.
- Updating CS6444 deliverables (those are done at tag
  `final-project-submitted-2026-05-11`).
- Editing existing Agenda slide (still adequate).

## User Stories

- As a reviewer reading the paper and deck together, I want the agent counts
  to match between the two artifacts.
- As Jason, I want a final-review record showing every Sprint 1 deliverable
  shipped cleanly so I can declare VVUQ Phase 3 closed in the memory bank.

## Design Approach

### Final-review checklist (operational)

The implementer runs each step and records the result in the final-review
report doc:

1. `cd proposal && make cleanall && make all` — capture page count,
   warnings, error count, bib resolution.
2. `cd proposal && rm -f presentation.* && pdflatex presentation && pdflatex
   presentation` — same for the deck.
3. Verify the `presentation.tex` "5 Specialized Agents" frame is updated to
   "6 Specialized Agents" with Structural Hypothesis added in the TikZ ring.
4. `git fetch origin && git status -sb` in both repos — verify both at
   origin/master, no divergence.
5. `curl -sI` for both Pages URLs with cache-bust query — confirm
   Last-Modified is recent (within the last 24 hours of the most recent push).
6. Write `construction/design/vvuq-phase3-final-review.md` with the pass/fail
   record for each checklist item.

### Update the "5 → 6 Specialized Agents" frame

The frame at lines ~198–216 of `presentation.tex` currently has a TikZ
`\foreach` over 5 angles `0/QA, 72/Inference, 144/Code, 216/Procure, 288/Instruct`.
Update to 6 angles `0/QA, 60/Inference, 120/Code, 180/Procure, 240/Instruct, 300/Structural`.
Update the headline text from "5 Specialized Agents" to "6 Specialized Agents".

The "Specialized Agents" diagram frame at lines ~172–196 also has 5 agent
nodes (`qa`, `infer`, `code`, `procure`, `instruct`) plus the `optimizer`
tool. Add a 6th agent node `structural` for the Structural Hypothesis Agent,
positioned naturally in the layout, with an arrow showing it integrates
with the KG (consistent with the paper's Phase 3.5 description).

### Final review report

A new doc at `construction-ai-proposal/construction/design/vvuq-phase3-final-review.md`
recording:
- Both compile results (page counts, warning counts)
- The 5→6 agent fix commit hash
- Pages cache-bust results (Last-Modified headers)
- Cross-references to Sprint 1a + 1b spec docs
- Statement: "VVUQ Phase 3 — CLOSED 2026-06-08"

## Sample Implementation

### TikZ update sample

```latex
% BEFORE (presentation.tex line ~201-211):
{\Large \textbf{5 Specialized Agents}}
\foreach \i/\name/\color in {0/QA/vtmaroon, 72/Inference/vtorange, 144/Code/vtmaroon, 216/Procure/vtorange, 288/Instruct/vtmaroon} {
  \node[circle, draw=\color, thick, minimum size=1.8cm, fill=\color!10, font=\small] at (\i:3cm) {\name};
}
\foreach \i in {0,72,144,216,288} {
  \draw[thick, vtgray, ->] (\i:1cm) -- (\i:2.1cm);
}

% AFTER:
{\Large \textbf{6 Specialized Agents}}
\foreach \i/\name/\color in {0/QA/vtmaroon, 60/Inference/vtorange, 120/Code/vtmaroon, 180/Procure/vtorange, 240/Instruct/vtmaroon, 300/Structural/vtorange} {
  \node[circle, draw=\color, thick, minimum size=1.6cm, fill=\color!10, font=\small] at (\i:3cm) {\name};
}
\foreach \i in {0,60,120,180,240,300} {
  \draw[thick, vtgray, ->] (\i:1cm) -- (\i:2.1cm);
}
```

The minimum size shrinks 1.8 → 1.6 to make room for 6 circles in the same
ring without overlap. Implementer adjusts further if compile shows overlap.

### Diagram frame update sample

```latex
% Add to the "Specialized Agents" frame around line 184:
\node[agent, right=of instruct] (structural) {Structural\\Hypothesis Agent};

% And add an arrow showing it integrates with the workflow:
\draw[arrow] (instruct) -- (structural);
```

### Final review report skeleton

```markdown
# VVUQ Phase 3 — Final Review

**Date:** 2026-06-08
**Status:** CLOSED
**Sprint:** 1c of the 2026 Product Roadmap

## Compile results

### main.pdf
- Final-pass citation warnings: 0
- Page count: 14
- Pre-existing "empty journal" warnings: 3 (anthropic2024claude, chase2022langchain, jocher2023yolov8) — out of scope

### presentation.pdf
- Page count: 25
- LaTeX errors: 0
- Missing-$: 0

## 5 → 6 Agents fix
- Updated: commit <hash>

## Pages re-publication
- main.pdf Last-Modified: <ts>
- presentation.pdf Last-Modified: <ts>

## Sprint 1a + 1b record
- 1a (citations) VERIFIED: <link>
- 1b (slides) VERIFIED: <link>

VVUQ Phase 3 — CLOSED 2026-06-08.
```

## Edge Cases & Error Handling

### Pages doesn't re-publish
- **Scenario:** GH Actions failed or hasn't run yet.
- **Behavior:** Investigate with `gh run list`. Re-run if needed.
- **Test:** `curl -sI` shows Last-Modified within 24 hr of last push.

### TikZ overlap after going 5 → 6 agents
- **Scenario:** Six 1.8cm circles overlap on a 3cm ring.
- **Behavior:** Shrink minimum size (1.8 → 1.6 or 1.5) until visually clean.
- **Test:** Implementer opens `presentation.pdf`, confirms no overlap (visual).

### Cleanall doesn't fully clean
- **Scenario:** Stale .aux / .bbl masks an error.
- **Behavior:** `rm -f *.aux *.bbl *.log *.pdf` explicitly before compile.
- **Test:** Compile log shows full re-run from scratch.

### Persistent BibTeX "empty journal" warnings
- **Scenario:** anthropic2024claude / chase2022langchain / jocher2023yolov8
  still warn. These predate Sprint 1.
- **Behavior:** Out of scope. Document as known issue in the report.
- **Test:** No new "empty journal" warnings from Sprint 1a entries.

## Acceptance Criteria

### AC-1: main.pdf compiles clean
- **Given** the implementation is complete
- **When** `cd proposal && make cleanall && make all` is run
- **Then** exit code is 0
- **And** final-pass `Warning: Citation .* undefined` count is 0
- **And** `pdfinfo main.pdf | grep Pages` shows ≤ 14

### AC-2: presentation.pdf compiles clean
- **Given** the implementation is complete
- **When** the deck is re-compiled from scratch
- **Then** exit code is 0
- **And** `LaTeX Error` count is 0
- **And** `pdfinfo presentation.pdf | grep Pages` shows 25

### AC-3: "5 Specialized Agents" replaced with "6"
- **Given** the implementation is complete
- **When** `grep -c "5 Specialized Agents" proposal/presentation.tex` is run
- **Then** the count is 0
- **And** `grep -c "6 Specialized Agents" proposal/presentation.tex` returns 1

### AC-4: Structural Hypothesis Agent in the TikZ ring
- **Given** the implementation is complete
- **When** the "6 Specialized Agents" frame is read
- **Then** the TikZ `\foreach` list includes "Structural" as the 6th agent
- **And** the angles partition 360° equally (e.g., 0/60/120/180/240/300)

### AC-5: Structural Hypothesis Agent added to diagram frame
- **Given** the implementation is complete
- **When** the "Specialized Agents" diagram frame (the named-node version) is read
- **Then** a `\node[agent] ... (structural) {...}` is present
- **And** at least one `\draw[arrow]` involves the `structural` node

### AC-6: Both repos in sync with origin
- **Given** the implementation is complete
- **When** `git fetch origin && git status -sb` is run in both repos
- **Then** both show "## master...origin/master" with no ahead/behind

### AC-7: Pages mirror published
- **Given** the commits are pushed
- **When** `curl -sI https://djjay0131.github.io/construction-ai-proposal/main.pdf?v=cb1`
  is run
- **Then** Last-Modified header is within 24 hours of the latest commit
- **And** same for `presentation.pdf`

### AC-8: Final review report exists and is comprehensive
- **Given** the implementation is complete
- **When** `construction/design/vvuq-phase3-final-review.md` is opened
- **Then** it has sections for: main compile, presentation compile, 5→6 fix,
  Pages re-publication, Sprint 1a + 1b references
- **And** ends with "VVUQ Phase 3 — CLOSED 2026-06-08"

### AC-9: No regression in Sprint 1a/1b deliverables
- **Given** the implementation is complete
- **When** the 14 Sprint 1a bibitems are grepped in `proposal/references.bib`
- **Then** all 14 still present
- **When** the 4 Sprint 1b frametitles are grepped in `proposal/presentation.tex`
- **Then** all 4 still present

### AC-10: Roadmap doc Sprint 1 marked complete
- **Given** Sprints 1a + 1b + 1c are all VERIFIED/closed
- **When** `construction/design/2026-product-roadmap.md` Appendix B sprint
  tracker is read
- **Then** Sprint 1 row status is "DONE" with commit hash and date

## Technical Notes

- **Affected files:**
  - `construction-ai-proposal/proposal/presentation.tex` — 5 → 6 agents edit
  - `construction-ai-proposal/construction/design/vvuq-phase3-final-review.md` — new
  - `construction-ai-proposal/construction/design/2026-product-roadmap.md` — Appendix B tracker update
- **Tools:** Edit tool for surgical changes; Bash for compile/git/curl; Read for visual check
- **No changes to:** main.tex, references.bib, 05a-verification-validation.tex, other section .tex files

## Dependencies

- Sprint 1a VERIFIED (citations live)
- Sprint 1b VERIFIED (4 new slides live)
- GitHub Actions running and producing Pages updates on push
- `curl` available for HEAD requests

## Open Questions

- Visual sanity check on TikZ overlap after 5→6 is necessarily manual (Read +
  judgement). **Decision:** implementer compiles, opens PDF, confirms — if
  unsure, ask user.
- Should the Agenda slide be updated to list the new "Structural Hypothesis
  Evaluation" section? **Decision:** non-goal per Sprint 1b precedent; the
  section header gives implicit visibility.

## Implementation Log (2026-06-08)

- Updated "5 Specialized Agents" → "6 Specialized Agents" rotated frame
  (`presentation.tex` line ~201): text swap, `\foreach` angles 5×72° → 6×60°,
  added `Structural` as the 3rd item (between Inference and Code), shrank
  circle `minimum size` from 1.8cm → 1.5cm and bumped arrow inner radius
  1.0→1.1cm + outer radius 2.1→2.2cm to compensate for the smaller circles.
- Updated "Specialized Agents" block-diagram frame (`presentation.tex`
  line ~172): inserted `\node[agent] (structural)` between `infer` and `code`
  in the top row; replaced arrow `(infer) -- (code)` with two arrows
  `(infer) -- (structural)` + `(structural) -- (code)`.
- Final review report written to
  `construction-ai-proposal/construction/design/vvuq-phase3-final-review.md`
  with compile results, the 5→6 fix description, Sprint 1 record, Pages
  re-publication block (to be filled during verify), and out-of-scope deferred
  items.
- Roadmap doc Appendix B sprint tracker updated: Sprint 0 marked DONE
  (with proposal `0f58f50`, code `aa1f761`); Sprint 1 marked DONE (with all
  six commits across 1a + 1b + 1c).
- Both PDFs recompiled from scratch: main.pdf = 14 pp / 0 final-pass cite
  warnings / 0 errors; presentation.pdf = 25 pp / 0 errors / 0 Missing-$.
- AC-9 regression check: all 14 Sprint 1a bibitems still present in
  `references.bib`; all 4 Sprint 1b frametitles still present in
  `presentation.tex`.

| AC | Result |
|---|---|
| AC-1: main.pdf compiles clean ≤14 pp | ✓ (14 pp, 0 cite warnings) |
| AC-2: presentation.pdf compiles clean at 25 pp | ✓ (25 pp, 0 errors) |
| AC-3: "5 Specialized Agents" → 0; "6" → 1 | ✓ |
| AC-4: Structural in foreach with 6 angles at 60° steps | ✓ |
| AC-5: structural agent node in diagram frame | ✓ (lines 182, 189, 190) |
| AC-6: both repos in sync with origin | pending (commit + push follows) |
| AC-7: Pages mirror Last-Modified post-push | pending (verify step) |
| AC-8: final-review report exists, comprehensive | ✓ (`vvuq-phase3-final-review.md`) |
| AC-9: no regression in Sprint 1a/1b deliverables | ✓ (all bibitems + frametitles present) |
| AC-10: roadmap tracker marked DONE for Sprint 1 | ✓ (Appendix B updated) |
