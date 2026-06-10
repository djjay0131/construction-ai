"""Health endpoints surfacing runtime state of the Knowledge Graph integration.

Cloud Run + the CD smoke-test rely on this to verify the KG initialization
sequence in ``app.main`` ran correctly. We always return HTTP 200 with a JSON
body — never 503 — so a misconfigured Aura doesn't cause Cloud Run to flag
the revision as unhealthy and stop sending traffic. The takeoff API still
serves via the ``DEFAULT_LUMBER_SPECS`` fallback even when KG is in
``error`` mode.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/kg")
def kg_health() -> dict:
    """Return a small JSON payload describing the KG runtime state.

    Three possible ``kg_status`` values:

    * ``"disabled"`` — ``NEO4J_URI`` is empty (early-dev posture; KG init
      was deliberately skipped at startup).
    * ``"ready"``    — Aura was reachable at startup, seeds ran, and the
      in-memory ``_lumber_specs_cache`` is populated.
    * ``"error"``    — ``NEO4J_URI`` was set but startup verify/seed/load
      failed; the cache is empty; the takeoff API falls back to
      ``DEFAULT_LUMBER_SPECS``.
    """
    # Lazy import to avoid circular: main imports the router; the router
    # reaches back into main's module-level state on each request.
    from app import main as main_module

    cache = main_module._lumber_specs_cache
    loaded = len(cache)

    if not settings.NEO4J_URI:
        return {"kg_status": "disabled", "lumber_specs_loaded": loaded}
    if main_module._kg_client is None or loaded == 0:
        return {"kg_status": "error", "lumber_specs_loaded": loaded}
    return {"kg_status": "ready", "lumber_specs_loaded": loaded}
