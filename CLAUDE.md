# Construction.AI - Implementation Repository

## Project Overview

This is the **implementation repository** for Construction.AI - an AI-driven material takeoff and construction recommendations system. This repo contains the working prototype and production code.

**Related Repository:** [construction-ai-proposal](../construction-ai-proposal/) - Research proposal and academic documentation

## Documentation System

**IMPORTANT:** This project uses a Memory Bank documentation system. On context reset, read ALL files in `memory-bank/` to restore full project context.

### Quick Start

1. Read `memory-bank/activeContext.md` for current state
2. Read `memory-bank/progress.md` for task status
3. Read `memory-bank/projectbrief.md` for core objectives

### Memory Bank Files

| File | Purpose |
|------|---------|
| `projectbrief.md` | Core objectives and requirements |
| `productContext.md` | Problem statement and user needs |
| `techContext.md` | Technical stack and details |
| `systemPatterns.md` | Architecture patterns |
| `activeContext.md` | Current focus and next steps |
| `progress.md` | Task completion tracking |
| `phases.md` | Phase coordination |
| `architecturalDecisions.md` | Key decisions (ADR format) |

## Session Notes

- **Started:** 2026-02-03
- **Status:** Implementation Active
- **Last Updated:** 2026-02-03

## Repository Structure

```
construction-ai/
├── backend/           # Python FastAPI backend
├── frontend/          # React frontend
├── datascience/       # ML models and notebooks
├── data/              # Sample data files
├── docs/              # Technical documentation
├── files/             # Uploaded files storage
├── construction/      # Sprint planning and design docs
├── memory-bank/       # Project context documentation
└── .claude/agents/    # AI agent configurations
```

## Current Implementation Status

### Working Components

- [ ] Plan parsing (PDF/DXF extraction)
- [ ] Component inference
- [ ] Knowledge Graph (Neo4j)
- [ ] Cut optimization (OR-Tools)
- [ ] Code compliance checking
- [ ] Build instruction generation

### Tech Stack

- **Backend:** Python, FastAPI
- **Frontend:** React, TypeScript
- **Database:** Neo4j (Knowledge Graph)
- **ML:** PyTorch, OpenCV, EasyOCR
- **Optimization:** OR-Tools

## Link to Proposal

This implementation follows the architecture defined in the proposal:

- **Proposal Repo:** `../construction-ai-proposal/`
- **Published Proposal:** https://djjay0131.github.io/construction-ai-proposal/
- **Architecture Reference:** `../construction-ai-proposal/proposal/sections/02-architecture.tex`

## Sync with Proposal

The `memory-bank/` and `construction/` folders are synchronized with the proposal repository to maintain consistency. Use the cross-project sync agent to keep both repos aligned.

## Development Commands

```bash
# Start all services
./launch.sh

# Or use docker-compose
docker-compose up -d

# View logs
docker-compose logs -f
```

## Context

This file provides quick session tracking. For comprehensive project context, refer to the `memory-bank/` folder.
