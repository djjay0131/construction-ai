# Sprint 0: Memory-Bank Refresh (Both Repos)

**Status:** VERIFIED
**Date:** 2026-06-06
**Implemented:** 2026-06-06
**Verified:** 2026-06-07
**Author:** Jason Cusati (with AI assistance)
**Roadmap source:** `construction-ai-proposal/construction/design/2026-product-roadmap.md`

## Problem

Both repos' memory-bank files have drifted out of sync with reality after the
CS6444 V&V semester project completed and we pivoted back to product roadmap work.

- `construction-ai-proposal/memory-bank/activeContext.md` last updated 2026-02-28.
  Still claims "VVUQ Phase 2 PR #7 pending merge" (actually merged 2026-02-28) and
  has no awareness of HW3 final review (PR #9), HW4, HW5, or Final Project (submitted
  2026-05-11 at tag `final-project-submitted-2026-05-11`).
- `construction-ai-proposal/memory-bank/progress.md` last updated 2026-02-28. Missing
  all CS6444 work after that date.
- `construction-ai-proposal/memory-bank/phases.md` last updated 2026-02-27. No phase
  registered for CS6444 final project or for the new product roadmap.
- `construction-ai/memory-bank/activeContext.md` last updated 2026-05-11. Mostly
  accurate through Final Project submission but "Immediate Next Steps" still says
  "Implementation sprint review" without naming the actual sprint plan; "Repository
  Relationship" section has stranded orphan bullets from an older structure.

A future Claude session reading these files will be misled about project state and
"Immediate Next Steps".

## Goals

- Both repos' `activeContext.md` files reflect 2026-06-06 state: CS6444 done,
  pivoting to product roadmap, Sprint 0 in progress, full sprint sequence listed.
- Proposal repo's `progress.md` records HW3 final review + HW4 + HW5 + Final
  Project milestones with dates and PR refs.
- Proposal repo's `phases.md` registers Phase 9 (CS6444 Final Project — Complete)
  and Phase 10 (Product Roadmap — In Progress).
- Code repo's `activeContext.md` orphan bullets cleaned up, "Immediate Next Steps"
  points to the roadmap doc.
- Both repos' files reference
  `construction/design/2026-product-roadmap.md` as the source of truth for next work.

## Non-Goals

- Rewriting accurate historical content. Surgical edits only — don't churn
  sections that are still correct.
- Updating CLAUDE.md, README.md, or other non-memory-bank files.
- Updating `construction-ai/memory-bank/{progress,phases}.md` (already accurate
  through 2026-05-11; only `activeContext.md` needs the forward-looking update).
- Pushing to origin — Sprint 0 done criteria is "committed to master". Push is
  the user's call.

## User Stories

- As a future Claude session, I want `activeContext.md` to tell me the current
  work phase and the next sprint, so I can resume work without re-deriving state.
- As Jason, I want both memory banks to point at the roadmap doc so the
  6-sprint plan is the canonical next-actions source.

## Design Approach

### Files Modified

1. `construction-ai-proposal/memory-bank/activeContext.md`
   - Replace "Last Updated" date.
   - Replace "Current Work Phase" section (currently claims VVUQ Phase 2 pending).
   - Replace "Immediate Next Steps" section.
   - Append a "2026-06-06 entry" naming Sprint 1 as the next sprint.

2. `construction-ai-proposal/memory-bank/progress.md`
   - Update "Last Updated" date.
   - Update top-line "Project Status:" header.
   - Add four "Completed Work" entries (HW3 final review PR #9, HW4, HW5, Final
     Project) — short entries that point to the construction-ai memory bank
     for technical detail (avoids duplication).

3. `construction-ai-proposal/memory-bank/phases.md`
   - Update "Last Updated" date.
   - Mark Phase 5 (VVUQ Integration) as COMPLETE (all 3 sub-phases done).
   - Register Phase 9 (CS6444 Final Project — Complete, submitted 2026-05-11).
   - Register Phase 10 (Product Roadmap — In Progress, started 2026-06-06).

4. `construction-ai/memory-bank/activeContext.md`
   - Update "Last Updated" date.
   - Rewrite "Current Work Phase" — pivot from CS6444 to product roadmap.
   - Replace "Immediate Next Steps" with sprint sequence pointing to roadmap doc.
   - Remove orphan bullets in the "Repository Relationship" section.

### Source of truth

The roadmap doc at
`construction-ai-proposal/construction/design/2026-product-roadmap.md`
(committed 2026-06-06, commit ae095ae) is the source of truth. Memory bank
files reference it; they should NOT duplicate its content. If the roadmap
changes, only the reference needs to stay current — not the duplicated content.

### Commit strategy

- Two separate commits (one per repo). Each commit touches only that repo's
  memory bank.
- Commit messages reference the roadmap doc commit (ae095ae proposal /
  06d7e0e code) for traceability.

## Sample Implementation

### Proposal repo `activeContext.md` — replacement for "Current Work Phase"

```markdown
## Current Work Phase

**Pivot from CS6444 (DONE) to product roadmap execution**

CS6444 V&V semester project SUBMITTED at tag `final-project-submitted-2026-05-11`
(construction-ai master @ 63f3d7a). HW3-final-review (PR #9), VVUQ Phase 2
(PRs #5, #6, #7) all merged. The IEEE proposal paper and Pages mirror are
stable at proposal-repo master @ 2dc762e.

**Next:** Execute the 6-sprint product roadmap at
`construction/design/2026-product-roadmap.md` (committed 2026-06-06, commit
ae095ae). Sprint 0 (memory-bank refresh, this work) is in-progress.

**Sprint sequence:**
- Sprint 0 — Memory-bank refresh (both repos) — in-progress
- Sprint 1 — VVUQ Phase 3 closeout: 4 slides + 10-15 citations + final review
- Sprint 2 — Neo4j Setup on GCP + CI/CD bootstrap
- Sprint 3 — Raster/Scanned Drawing Support
- Sprint 4 — OCR Dimension Extraction
- Sprint 5 — Phase 1 integration smoke test
```

### Proposal repo `progress.md` — new "Recent Work" entries (top of file)

```markdown
### Final Project — CS6444 V&V (2026-05-11)
- Submitted at construction-ai tag `final-project-submitted-2026-05-11`
- 13-page Project report, Microllam 2.0E baseline, 25 web-verified bib refs
- Live: <https://djjay0131.github.io/construction-ai-proposal/VVSC_Cusati_Chuang_Project.pdf>
- See construction-ai memory-bank/activeContext.md for technical detail

### HW5 (2026-04-19)
- MAVM validation metric at n=10/25/100 LHS
- Live: <https://djjay0131.github.io/construction-ai-proposal/VVSC_Cusati_Chuang_HW5.pdf>

### HW4 (2026-04-01)
- GCI + U_NUM budget per Roy/Celik framework
- Live: <https://djjay0131.github.io/construction-ai-proposal/VVSC_Cusati_Chuang_HW4.pdf>

### HW3 final review (PR #9, 2026-03-07)
- Added citations, justified Option 2, improved tone
- Merged to master
```

### Proposal repo `phases.md` — Phase Registry additions

```markdown
| 9: CS6444 Final Project | Complete | VVSC_Cusati_Chuang_Project.pdf, 25 verified bib refs | 2026-05-11 |
| 10: Product Roadmap (proposal Phase 1) | In Progress | 6-sprint sequence per 2026-product-roadmap.md | TBD |
```

Mark Phase 5 row status: `Complete` (all 3 sub-phases done — Phase 2 PRs all
merged 2026-02-28; Phase 3 deferred but now subsumed into roadmap Sprint 1).

### Code repo `activeContext.md` — replacement for "Current Work Phase"

```markdown
## Current Work Phase

**Returning to product roadmap after CS6444 Final Project submission**

CS6444 V&V semester project SUBMITTED at tag `final-project-submitted-2026-05-11`.
All HW2-5 + Final Project complete and live on Pages.

**Next:** Execute the 6-sprint product roadmap at
`../construction-ai-proposal/construction/design/2026-product-roadmap.md`
(committed 2026-06-06). Sprint 0 (memory-bank refresh, this work) in-progress.

Sprint sequence:
1. Sprint 0 — Memory-bank refresh (both repos) — in-progress
2. Sprint 1 — VVUQ Phase 3 closeout (proposal repo)
3. Sprint 2 — Neo4j Setup on GCP + CI/CD bootstrap (implements
   `llm/features/neo4j-setup.md`)
4. Sprint 3 — Raster/Scanned Drawing Support
5. Sprint 4 — OCR Dimension Extraction
6. Sprint 5 — Phase 1 integration smoke test
```

## Edge Cases & Error Handling

### Memory bank file missing
- **Scenario:** A memory-bank file we expect to edit doesn't exist.
- **Behavior:** Implementation fails fast with a clear error. Memory bank
  structure is a project convention; missing files are a separate problem.

### Roadmap doc not found
- **Scenario:** The roadmap doc this spec references doesn't exist.
- **Behavior:** Fail. The roadmap is the source of truth; without it, the
  memory-bank entries point to nothing.
- **Mitigation:** Verify the roadmap exists at commit ae095ae before starting.

### Concurrent edits during memory-bank refresh
- **Scenario:** Another agent is editing the same files at the same time.
- **Behavior:** Single-author session; not a real concern. Implementation runs
  serially.

### CS6444 dates need adjustment after the fact
- **Scenario:** A historical date in the new "Recent Work" entries turns out
  to be wrong.
- **Behavior:** Memory entries are versioned in git; fix in a follow-up commit.

## Acceptance Criteria

### AC-1: Proposal `activeContext.md` reflects current state
- **Given** the file is opened
- **When** the "Current Work Phase" section is read
- **Then** it does NOT mention "VVUQ Phase 2 PR #7 pending merge"
- **And** it mentions CS6444 submission tag `final-project-submitted-2026-05-11`
- **And** it references `construction/design/2026-product-roadmap.md`
- **And** "Last Updated" is 2026-06-06

### AC-2: Proposal `activeContext.md` lists the sprint sequence
- **Given** the file is opened
- **When** the "Current Work Phase" or equivalent forward-looking section is read
- **Then** all six sprints (0–5) are named in order

### AC-3: Proposal `progress.md` records CS6444 final state
- **Given** the file is opened
- **When** "Completed Work" / "Recent Work" entries are read
- **Then** there are entries for HW3 final review (PR #9), HW4, HW5, and
  Final Project, each with a date and a Pages URL

### AC-4: Proposal `phases.md` registers Phase 9 and Phase 10
- **Given** the file is opened
- **When** the Phase Registry table is read
- **Then** Phase 9 (CS6444 Final Project) is listed with status "Complete" and
  date 2026-05-11
- **And** Phase 10 (Product Roadmap) is listed with status "In Progress" and
  date 2026-06-06

### AC-5: Proposal `phases.md` marks Phase 5 (VVUQ) as Complete
- **Given** the Phase Registry table
- **When** Phase 5 row is read
- **Then** status is "Complete" (not "In Progress")

### AC-6: Code `activeContext.md` pivots to product roadmap
- **Given** the file is opened
- **When** "Current Work Phase" section is read
- **Then** it identifies CS6444 as DONE and points to the roadmap doc at
  `../construction-ai-proposal/construction/design/2026-product-roadmap.md`
- **And** "Last Updated" is 2026-06-06

### AC-7: Code `activeContext.md` orphan bullets removed
- **Given** the file is opened
- **When** the "Repository Relationship" section is read
- **Then** no stranded bullets exist (e.g. "2. Map current implementation to
  proposal architecture" that appears outside any numbered list)

### AC-8: Both repos' memory-bank changes committed separately
- **Given** the work is complete
- **When** `git log --oneline -2` is run in each repo
- **Then** there is a memory-bank-refresh commit at HEAD in each repo
- **And** the commit messages reference the roadmap doc

### AC-9: No accidental edits to non-memory-bank files
- **Given** the work is complete
- **When** `git diff HEAD~1 --name-only` is run in each repo
- **Then** only files in `memory-bank/` are listed (one repo) or only the
  expected memory-bank file (the other repo)

### AC-10: Read-pass through each updated file produces no broken cross-refs
- **Given** the updated memory-bank files
- **When** read top-to-bottom
- **Then** every relative link points to a file that exists, and every
  referenced commit hash is reachable

## Technical Notes

- **Files affected (proposal repo):**
  - `memory-bank/activeContext.md`
  - `memory-bank/progress.md`
  - `memory-bank/phases.md`
- **Files affected (code repo):**
  - `memory-bank/activeContext.md`
- **Editor tool:** Use the Edit tool for surgical replacements (preserves
  unchanged content). Avoid Write — would force a full re-author and risk
  losing context.
- **Validation:** After each edit, re-read the modified file and check the
  changed section reads cleanly in context. After all edits in a repo,
  `git diff` to confirm only memory-bank/ files were touched.

## Dependencies

- Roadmap doc must exist at
  `construction-ai-proposal/construction/design/2026-product-roadmap.md`
  (already committed at ae095ae).
- ROADMAP pointer must exist at `construction-ai/llm/features/ROADMAP.md`
  (already committed at 06d7e0e).
- Both repos must be on master with clean working trees before starting.

## Open Questions

- None. This sprint is text-edit only; constraints and conventions are fully
  spelled out above.
