# 2026 Product Roadmap (Pointer)

**The canonical roadmap doc lives in the proposal repo:**

  `construction-ai-proposal/construction/design/2026-product-roadmap.md`

This pointer exists so anyone working in `construction-ai/` can find it.

## Quick Summary

Six discrete sprints, burst/opportunistic cadence, GCP-first deploy (Cloud Run +
AuraDB Free), each self-contained with pre/build/test/deploy/done criteria.

1. **Sprint 0** — Memory-bank refresh (both repos)
2. **Sprint 1** — VVUQ Phase 3 closeout (proposal repo: 4 slides + 10–15 citations + final review)
3. **Sprint 2** — Neo4j Setup on GCP + CI/CD bootstrap (implements `neo4j-setup.md`)
4. **Sprint 3** — Raster/Scanned Drawing Support (implements `raster-scanned-drawing-support.md`)
5. **Sprint 4** — OCR Dimension Extraction (implements `ocr-dimension-extraction.md`)
6. **Sprint 5** — Phase 1 integration smoke test against 2–3 plan sets

After Sprint 5: pick from `BACKLOG.md`. Top candidates: Header Sizing (3.2),
Cut List Optimization (4.1).

See the canonical doc for full per-sprint detail, cross-cutting infrastructure
decisions, open questions, and the sprint-status tracker.
