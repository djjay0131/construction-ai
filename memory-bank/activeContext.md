# Active Context

**Last Updated:** 2026-02-03

## Current Work Phase

**Implementation Setup - Synced with Proposal Repository**

This is the **implementation repository** for Construction.AI. Documentation has been synchronized from the proposal repository to maintain consistency.

## Current State

**Implementation Repository Status:**

- Backend: Python FastAPI (existing prototype)
- Frontend: React TypeScript (existing prototype)
- Docker: docker-compose configuration present
- Documentation: Synced from proposal repo (2026-02-03)

**Proposal Repository Status (see ../construction-ai-proposal/):**

- 12-page IEEE conference paper
- 21-slide Beamer presentation
- VVUQ integration Phase 1 complete, Phases 2-3 in progress
- Published at: [GitHub Pages](https://djjay0131.github.io/construction-ai-proposal/)

## Repository Relationship

| Repository | Purpose | Status |
| ---------- | ------- | ------ |
| construction-ai | Implementation code | Active development |
| construction-ai-proposal | Research proposal | VVUQ integration ongoing |

**Sync Strategy:** Both repos share memory-bank and construction folder patterns. A cross-project sync agent maintains consistency between documentation.

## Implementation Architecture (from Proposal)

**KG-Centered Architecture**: Knowledge Graph (Neo4j) as the backbone for grounded, repeatable decisions.

**Multi-Agent System** (5 specialized agents):

1. Extraction QA Agent - Validates plan parsing
2. Component Inference Agent - Identifies structural components
3. Code & Compliance Agent - Checks building codes
4. Procurement Agent - Generates BOMs
5. Instruction Generation Agent - Creates build instructions

**Data Flow:**

```
Plans → Extraction → Normalization → Inference → Optimization → Export
                          ↓
                    Knowledge Graph
```

## Immediate Next Steps

**Implementation Tasks:**

1. Review existing backend/frontend code
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
