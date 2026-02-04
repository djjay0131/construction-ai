# Sprints - Implementation Development

This folder contains sprint documents for Construction.AI implementation development.

## Current Sprint

**Sprint 01: Foundation Setup** - Not Started

## Sprint Overview

| Sprint | Focus | Status | Target |
|--------|-------|--------|--------|
| Sprint 01 | Foundation Setup | 🔲 Not Started | TBD |
| Sprint 02 | Knowledge Graph | 🔲 Planned | TBD |
| Sprint 03 | Agent Framework | 🔲 Planned | TBD |
| Sprint 04 | Integration | 🔲 Planned | TBD |

## Implementation Phases

Based on the proposal architecture, implementation follows these phases:

### Phase 1: KG Foundation

- Neo4j database setup
- Schema definition (components, materials, fasteners, codes)
- Seed data for initial testing
- Basic CRUD operations

### Phase 2: Plan Parsing

- PDF extraction pipeline
- DXF parsing capability
- Component detection (walls, doors, windows)
- Dimension extraction (OCR)

### Phase 3: Agent Framework

- Base agent architecture
- Extraction QA Agent
- Component Inference Agent
- Inter-agent communication via KG

### Phase 4: Optimization & Compliance

- OR-Tools cut optimization
- Code compliance checking (IRC)
- Build instruction generation
- Provenance tracking

## Reference Architecture

See proposal for detailed architecture:

- Architecture: `../construction-ai-proposal/proposal/sections/02-architecture.tex`
- Knowledge Graph: `../construction-ai-proposal/proposal/sections/03-knowledge-graph.tex`
- Agentic Workflow: `../construction-ai-proposal/proposal/sections/05-agentic-workflow.tex`
- Published: [GitHub Pages](https://djjay0131.github.io/construction-ai-proposal/)

## Existing Code Review

Before starting sprints, review existing implementation:

- `backend/` - Python FastAPI backend
- `frontend/` - React TypeScript frontend
- `datascience/` - ML models and notebooks

## Sprint Document Template

```markdown
# Sprint NN: {Focus}

## Goals
- Goal 1
- Goal 2

## Tasks
- [ ] Task 1
- [ ] Task 2

## Acceptance Criteria
- Criteria 1
- Criteria 2

## Notes
```

## Workflow

1. **Before sprint:** Review proposal architecture for guidance
2. **During sprint:** Update task checkboxes, commit frequently
3. **After sprint:** Update progress.md, sync with proposal repo if needed
