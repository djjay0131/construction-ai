# Construction Folder - Implementation Repository

## Purpose

This folder tracks implementation development and sprint planning for the Construction.AI system. It maintains synchronization with the proposal repository for architectural consistency.

## Project Context

**Project:** Construction.AI Implementation
**Goal:** Build the KG-centered construction takeoff system defined in the proposal
**Status:** Implementation setup, synced with proposal repo

**Related Repository:** [construction-ai-proposal](../construction-ai-proposal/) - Research proposal and academic documentation

## Structure

### design/

Contains design documents (synced from proposal):

- `proposal-structure.md` - Document organization
- `novelty-analysis.md` - Key contributions
- `literature-review.md` - Bibliography analysis
- `vvuq-integration-plan.md` - Physics-based structural analysis plan

### requirements/

Contains quality requirements and acceptance criteria:

- `submission-checklist.md` - Pre-submission requirements (proposal)
- `section-requirements.md` - Quality standards

### sprints/

Contains sprint planning documents:

- Current sprint status
- Completed tasks
- Remaining work

### spec_builder.md

Template for documenting feature specifications.

## Repository Relationship

| Repository | Purpose | Location |
| ---------- | ------- | -------- |
| construction-ai | Implementation code | This repo |
| construction-ai-proposal | Research proposal | `../construction-ai-proposal/` |

**Sync Strategy:** Documentation patterns shared between repos. Cross-project sync agent maintains consistency.

## Implementation Architecture

From the proposal, the system implements:

1. **Knowledge Graph (Neo4j)** - Central data store for construction knowledge
2. **Multi-Agent System** - 5 specialized agents for different tasks
3. **Plan Parsing** - PDF/DXF extraction with computer vision
4. **Cut Optimization** - OR-Tools for material optimization
5. **Code Compliance** - IRC residential building code checks

## Current Status

### Documentation Setup - COMPLETE (2026-02-03)

- [x] Memory-bank folder synced from proposal
- [x] Construction folder synced from proposal
- [x] Agents folder synced from proposal
- [x] CLAUDE.md created for implementation context
- [x] Cross-project sync agent created

### Implementation Status

**Existing Components:**

- Backend: Python FastAPI (prototype)
- Frontend: React TypeScript (prototype)
- Docker: docker-compose configuration

**To Implement (from Proposal):**

- [ ] Neo4j Knowledge Graph schema
- [ ] 5-agent agentic workflow
- [ ] OR-Tools cut optimization
- [ ] Code compliance checking
- [ ] Build instruction generation

## Workflow

1. **Before implementing:** Review proposal architecture
2. **When building features:** Check design/ for specifications
3. **During development:** Update progress in sprints/
4. **After completing:** Sync documentation with proposal repo

## Key References

| Resource | Location |
| -------- | -------- |
| Proposal PDF | [GitHub Pages](https://djjay0131.github.io/construction-ai-proposal/) |
| Architecture | `../construction-ai-proposal/proposal/sections/02-architecture.tex` |
| KG Design | `../construction-ai-proposal/proposal/sections/03-knowledge-graph.tex` |
| Agent Workflow | `../construction-ai-proposal/proposal/sections/05-agentic-workflow.tex` |
| VVUQ Plan | `design/vvuq-integration-plan.md` |

## Quick Start

```bash
# Start all services
./launch.sh

# Or use docker-compose
docker-compose up -d

# View logs
docker-compose logs -f
```
