# Sprint 2c: Aura Deploy + Smoke Test

**Status:** VERIFIED
**Date:** 2026-06-10
**Implemented:** 2026-06-10
**Verified:** 2026-06-10
**Author:** Jason Cusati (with AI assistance)
**Sprint:** 2c of 3 (2026 Product Roadmap Sprint 2 — Neo4j Setup on GCP)
**Depends on:** Sprint 2a + Sprint 2b VERIFIED

## Problem

Sprints 2a + 2b shipped a KG-aware backend and a Cloud Run + Artifact
Registry + Secret Manager + Workload Identity Federation pipeline. To close
out Sprint 2 of the 2026 Product Roadmap, the deployed service needs to be
verified end-to-end:

- **Cloud Run service is healthy** (responds to ``GET /``).
- **The KG initialization sequence ran correctly** at startup
  (verify_kg_connection → seed_kg → load_specs), so the
  ``DEFAULT_LUMBER_SPECS`` fallback path isn't silently masking a broken
  Aura connection.
- **The seed populated the expected 6 lumber specs**, retrievable via the
  in-memory cache.

There's no programmatic way today to ask the running service "is KG up?"
or "how many specs did you load?" — only the FastAPI startup logs surface
this, which is awkward to grep from CI and useless once the container has
restarted.

Sprint 2c adds:

1. A new ``/api/health/kg`` endpoint that returns a small JSON payload
   describing KG status and the loaded-specs count.
2. A ``backend/scripts/smoke_test.py`` script that hits a target URL and
   exits non-zero when the service isn't healthy.
3. A post-deploy ``smoke_test`` step in ``.github/workflows/cd.yml`` so
   every CD run validates the new revision before declaring success.
4. An ``infra/README.md`` section walking the operator through the
   one-time manual setup (Aura provisioning, secret population) and the
   first live smoke test.

## Goals

- ``GET /api/health/kg`` returns a small, stable JSON contract:
  ``{kg_status: "ready" | "disabled" | "error", lumber_specs_loaded: int}``.
  - ``ready`` — Aura reachable at startup, seeds ran, specs in cache.
  - ``disabled`` — ``NEO4J_URI`` was empty (early-dev posture).
  - ``error`` — Aura URI was set but startup verify/seed/load failed.
- ``smoke_test.py`` is a small Python script (httpx + argparse) that
  exercises ``GET /`` and ``GET /api/health/kg`` against a configurable
  URL and prints a 1-line PASS/FAIL summary.
- The script exits ``0`` only when both endpoints return 200 AND
  ``kg_status`` is ``ready`` (or ``disabled``, when the operator asks for
  that mode explicitly via ``--allow-disabled``).
- CD workflow runs the smoke test after ``gcloud run deploy`` succeeds,
  failing the CD run if the smoke test fails.
- Unit-test the script with mocked httpx so coverage is high enough to
  catch regressions without needing a live URL.
- Unit-test the endpoint via FastAPI ``TestClient`` so the contract is
  pinned.
- Operator README documents the AuraDB Free provisioning + Secret Manager
  population flow and how to run the smoke test from a developer machine.

## Non-Goals

- **End-to-end takeoff smoke test** (POSTing a DXF and validating a real
  BOM response) — out of scope for Sprint 2c; cost-benefit doesn't justify
  shipping a test DXF + the API plumbing. Future sprint, once raster /
  OCR features ship.
- **Provisioning AuraDB Free programmatically** — Aura Free signup is a
  manual web flow with no Terraform provider. Operator README documents
  it; the spec doesn't try to automate it.
- **End-to-end auth / multi-tenancy testing** — out of scope; auth doesn't
  exist yet (item 10.5 in BACKLOG).
- **Container image-size optimization** — see Sprint 2b commit; out of
  scope here.

## User Stories

- As Jason running CD on a master push, I want the smoke test to fail loud
  if the new revision is broken so I can roll back before users notice.
- As Jason debugging a "did the KG load?" question, I want a small JSON
  endpoint I can curl from my laptop without ssh-ing to the container.
- As a future operator, I want a runbook that walks me through Aura
  provisioning and the first smoke test without having to read the
  whole spec.

## Design Approach

### New endpoint: ``/api/health/kg``

Lives in a tiny new ``backend/app/api/health.py`` module so we don't bloat
``main.py``. Reads the module-level ``_lumber_specs_cache`` and
``_kg_client`` from ``app.main``, decides which of the three states applies,
and returns the JSON payload.

State decision logic:

```
if settings.NEO4J_URI == "":          # early-dev posture
    return {"kg_status": "disabled", "lumber_specs_loaded": len(cache)}
if _kg_client is None or len(cache) == 0:
    return {"kg_status": "error", "lumber_specs_loaded": len(cache)}
return {"kg_status": "ready", "lumber_specs_loaded": len(cache)}
```

The endpoint always returns HTTP 200 with the JSON body — clients
(including the smoke test) check the ``kg_status`` field. Returning 503
for the error case is tempting but makes Cloud Run flag the revision as
unhealthy and stop sending traffic. We want it to keep serving (with the
``DEFAULT_LUMBER_SPECS`` fallback) so the rest of the API stays available.

### Smoke-test script: ``backend/scripts/smoke_test.py``

CLI:

```
python -m scripts.smoke_test --url https://construction-ai-backend-xxx.run.app
python -m scripts.smoke_test --url https://... --allow-disabled    # for early-dev runs
```

Steps:

1. ``GET {url}/`` — expect HTTP 200.
2. ``GET {url}/api/health/kg`` — expect HTTP 200 + JSON with ``kg_status``.
3. Check ``kg_status`` is ``ready`` (or ``disabled`` when ``--allow-disabled``).
4. Print 1-line summary; exit 0 on success, 1 on any failure (with
   actionable error message).

Uses ``httpx`` (already pinned in Sprint 2b's requirements.txt fix). Reads
``--url`` from argparse. No env-var override — explicit URL on each invoke.

### CD workflow extension

Appends a step after the existing "Show service URL" step:

```yaml
- name: Smoke test the deployed revision
  run: |
    URL=$(gcloud run services describe "${SERVICE}" --region="${REGION}" --format='value(status.url)')
    pip install httpx
    python backend/scripts/smoke_test.py --url "$URL"
```

The step inherits the existing failure semantics — any non-zero exit
fails the CD run. The Cloud Run revision stays deployed (no auto-rollback);
operator decides whether to roll back manually based on what the smoke
test reported.

Note: ``--allow-disabled`` is NOT passed in CD — production deploys must be
``ready``. For early-dev runs where the operator hasn't populated Secret
Manager yet, they invoke the script locally with ``--allow-disabled``.

### Operator README addition

Two new sections in ``infra/README.md``:

- **AuraDB Free Provisioning** — step-by-step walk through console.neo4j.io
  signup, the bolt URI format, and the Aura-generated password copy.
- **First Live Smoke Test** — three commands: populate the three
  Secret Manager secrets, force a new Cloud Run revision, run
  ``python backend/scripts/smoke_test.py --url $URL``.

### Unit tests

- ``backend/tests/test_health_endpoint.py`` — FastAPI ``TestClient``
  exercises all three KG states (``ready`` / ``disabled`` / ``error``) by
  monkey-patching ``app.main._lumber_specs_cache`` and ``_kg_client``.
- ``backend/tests/test_smoke_test_script.py`` — exercises the script's
  exit-code paths via ``subprocess`` (or by calling ``main()`` directly)
  with mocked httpx. Covers:
  - both endpoints return 200 + ready → exit 0
  - ``/`` returns 500 → exit 1
  - ``/api/health/kg`` returns ``kg_status: error`` → exit 1
  - ``kg_status: disabled`` without ``--allow-disabled`` → exit 1
  - ``kg_status: disabled`` with ``--allow-disabled`` → exit 0
  - network error → exit 1 with clear message

## Sample Implementation

```python
# === backend/app/api/health.py ===
from fastapi import APIRouter
from app.core.config import settings

router = APIRouter()


@router.get("/api/health/kg")
def kg_health():
    # Lazy import to avoid circular: main imports the router; the router
    # reaches back into main's module-level state on each request.
    from app import main
    cache = main._lumber_specs_cache
    if not settings.NEO4J_URI:
        return {"kg_status": "disabled", "lumber_specs_loaded": len(cache)}
    if main._kg_client is None or len(cache) == 0:
        return {"kg_status": "error", "lumber_specs_loaded": len(cache)}
    return {"kg_status": "ready", "lumber_specs_loaded": len(cache)}
```

```python
# === backend/scripts/smoke_test.py ===
"""Smoke-test a deployed Construction.AI backend.

Hits two endpoints and reports PASS/FAIL. Designed to be CI-friendly:
exit-0 on success, exit-1 on any failure, with a single-line summary
on the last printed line.

Usage:
    python backend/scripts/smoke_test.py --url https://example.run.app
    python backend/scripts/smoke_test.py --url ... --allow-disabled
"""

from __future__ import annotations

import argparse
import sys

import httpx


def smoke_test(url: str, allow_disabled: bool = False) -> int:
    """Return 0 on PASS, 1 on FAIL. Prints a single summary line last."""
    url = url.rstrip("/")

    try:
        root = httpx.get(f"{url}/", timeout=10.0)
        if root.status_code != 200:
            print(f"FAIL: GET / returned {root.status_code}")
            return 1

        kg = httpx.get(f"{url}/api/health/kg", timeout=10.0)
        if kg.status_code != 200:
            print(f"FAIL: GET /api/health/kg returned {kg.status_code}")
            return 1

        payload = kg.json()
        status = payload.get("kg_status")
        loaded = payload.get("lumber_specs_loaded")

        if status == "ready":
            print(f"PASS: kg_status=ready, lumber_specs_loaded={loaded}")
            return 0
        if status == "disabled" and allow_disabled:
            print(f"PASS: kg_status=disabled (allowed), lumber_specs_loaded={loaded}")
            return 0
        print(f"FAIL: kg_status={status}, lumber_specs_loaded={loaded}")
        return 1
    except httpx.HTTPError as exc:
        print(f"FAIL: HTTP error: {exc}")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Base URL of the backend service")
    parser.add_argument(
        "--allow-disabled",
        action="store_true",
        help="Pass when kg_status is 'disabled' (early-dev posture without Aura)",
    )
    args = parser.parse_args()
    return smoke_test(args.url, allow_disabled=args.allow_disabled)


if __name__ == "__main__":
    sys.exit(main())
```

## Edge Cases & Error Handling

### Cloud Run cold start during smoke test
- **Scenario:** First request after deploy may take 5-10s due to container
  cold start.
- **Behavior:** ``httpx.get(..., timeout=10.0)`` covers it. Cloud Run
  responds within a few seconds for FastAPI's minimal startup.
- **Test:** Manual; CI step's first request to ``/`` warms the container.

### Aura paused during smoke test
- **Scenario:** AuraDB Free idle-pauses after 30 days. After a long break,
  the next ``gcloud run deploy`` succeeds but startup verify fails →
  endpoint reports ``kg_status: error``.
- **Behavior:** Smoke test fails CD; operator un-pauses Aura via console,
  triggers a new revision, smoke test passes.
- **Test:** Covered by the ``kg_status: error`` unit test.

### NEO4J_URI set but invalid
- **Scenario:** Operator typoed the URI in Secret Manager.
- **Behavior:** Startup logs error; Cloud Run still healthy (no crash);
  endpoint returns ``kg_status: error``; smoke test fails.
- **Test:** Same path as Aura-paused test.

### Network blip during smoke test
- **Scenario:** Transient network error between CI runner and Cloud Run.
- **Behavior:** ``httpx.HTTPError`` caught; FAIL with message.
- **Test:** Covered by the network-error unit test.

### Operator forgot ``--allow-disabled`` for early-dev run
- **Scenario:** Running smoke test against a deploy without Secret Manager
  populated; service is ``disabled`` but operator didn't pass the flag.
- **Behavior:** FAIL with ``kg_status=disabled``. Operator re-runs with
  ``--allow-disabled``.
- **Test:** Both branches covered.

## Acceptance Criteria

### AC-1: Endpoint exists and is wired
- **Given** the backend is running
- **When** ``GET /api/health/kg`` is called
- **Then** HTTP 200 with JSON containing keys ``kg_status`` + ``lumber_specs_loaded``

### AC-2: Endpoint returns ``disabled`` when NEO4J_URI is empty
- **Given** ``settings.NEO4J_URI = ""``
- **When** the endpoint is called
- **Then** payload is ``{"kg_status": "disabled", "lumber_specs_loaded": 0}``

### AC-3: Endpoint returns ``ready`` when specs are loaded
- **Given** ``settings.NEO4J_URI != ""`` AND ``_lumber_specs_cache`` has 6 entries
- **When** the endpoint is called
- **Then** payload is ``{"kg_status": "ready", "lumber_specs_loaded": 6}``

### AC-4: Endpoint returns ``error`` when KG init failed
- **Given** ``settings.NEO4J_URI != ""`` AND ``_kg_client is None``
- **When** the endpoint is called
- **Then** payload is ``{"kg_status": "error", "lumber_specs_loaded": 0}``

### AC-5: smoke_test.py exits 0 on healthy ``ready`` response
- **Given** both endpoints return 200 + ``kg_status: ready``
- **When** ``python smoke_test.py --url ...`` is run
- **Then** exit code is 0; last printed line starts with ``PASS:``

### AC-6: smoke_test.py exits 1 on failure modes
- **Given** any of: ``/`` non-200, ``/api/health/kg`` non-200,
  ``kg_status`` is ``error``, ``kg_status`` is ``disabled`` without
  ``--allow-disabled``, network error
- **When** ``python smoke_test.py --url ...`` is run
- **Then** exit code is 1; last printed line starts with ``FAIL:``

### AC-7: ``--allow-disabled`` flag accepts disabled mode
- **Given** ``kg_status: disabled``
- **When** ``python smoke_test.py --url ... --allow-disabled`` is run
- **Then** exit code is 0; last printed line starts with ``PASS:``

### AC-8: CD workflow runs the smoke test after deploy
- **Given** the CD workflow is read
- **When** the steps after ``Deploy to Cloud Run`` are listed
- **Then** a ``Smoke test`` step exists that runs ``smoke_test.py`` with the
  Cloud Run service URL

### AC-9: README has Aura provisioning + smoke test instructions
- **Given** ``infra/README.md`` is read
- **When** the sections "AuraDB Free Provisioning" and "First Live Smoke
  Test" are searched for
- **Then** both exist and document the steps end-to-end

### AC-10: Unit-test coverage ≥85% on the new code; Sprint 2a/2b regression check
- **Given** the implementation is complete
- **When** ``pytest --cov=app.api.health --cov=scripts.smoke_test`` is run
- **Then** line coverage is ≥85% for both modules
- **And** the 30 Sprint 2a tests still pass

## Technical Notes

- **Affected files:**
  - ``backend/app/api/health.py`` (new)
  - ``backend/app/main.py`` — wire the router
  - ``backend/scripts/__init__.py`` (new)
  - ``backend/scripts/smoke_test.py`` (new)
  - ``backend/tests/test_health_endpoint.py`` (new)
  - ``backend/tests/test_smoke_test_script.py`` (new)
  - ``.github/workflows/cd.yml`` — add smoke-test step
  - ``infra/README.md`` — Aura section + smoke-test section
- **No new runtime dependencies** — httpx is already in requirements.txt
  (added in Sprint 2b's Gate 1 fix).
- **Existing test framework** — pytest, established by Sprint 2a.

## Dependencies

- Sprint 2a VERIFIED (KG package + lumber refactor).
- Sprint 2b VERIFIED (CI/CD + Terraform + Cloud Run).
- User-side (for the live smoke test, NOT for spec verification):
  1. Run ``terraform apply`` from ``infra/``.
  2. Capture outputs, set GH secrets ``WIF_PROVIDER`` + ``CI_SA_EMAIL``.
  3. Provision AuraDB Free at console.neo4j.io.
  4. Populate the three Secret Manager secrets with Aura URI / user / password.
  5. Push to master → CD deploys + smoke-tests → live URL is KG-backed.

## Open Questions

- Should the health endpoint surface the Cloud Run revision + git SHA in
  the payload? **Decision:** out of scope for Sprint 2c; useful for future
  observability work. Sprint 2c keeps the payload minimal.
- Should ``smoke_test.py`` retry once on a transient network error?
  **Decision:** no — Cloud Run is reliable enough that a single retry just
  masks real failures. If we hit transient errors in practice, add retries
  in a follow-up.
- Add a ``--timeout`` flag? **Decision:** hardcode 10s for now; bump in a
  follow-up if Cloud Run cold starts ever exceed it.

## Implementation Log (2026-06-10)

**Files created:**
- `backend/app/api/health.py` — APIRouter with `@router.get("/kg")` returning
  ``{kg_status, lumber_specs_loaded}``. Lazy-imports ``app.main`` at request
  time to avoid circular dependency. Always returns HTTP 200 so Cloud Run
  doesn't quarantine the revision.
- `backend/scripts/__init__.py` — package marker.
- `backend/scripts/smoke_test.py` — argparse + httpx CLI. ``smoke_test()``
  helper returns exit code; ``main(argv)`` is the argparse entrypoint.
- `backend/tests/test_health_endpoint.py` — 7 tests covering all 3 kg_status
  branches via stubbed ``app.main`` in ``sys.modules`` and a minimal
  FastAPI test app (avoids the heavy backend import chain).
- `backend/tests/test_smoke_test_script.py` — 10 tests covering all exit-1
  paths, the PASS path, ``--allow-disabled`` toggle, URL normalization,
  and the ``main()`` argparse layer.

**Files modified:**
- `backend/app/main.py` — added `health` to the api imports + included the
  router at `prefix="/api/health"` with `tags=["Health"]`.
- `.github/workflows/cd.yml` — appended 4 steps after "Show service URL":
  capture URL into `$GITHUB_OUTPUT`, set up Python 3.11, `pip install
  httpx`, run `smoke_test.py`. Smoke-test step fails CD when the deployed
  revision isn't `ready`.
- `infra/README.md` — added "7. AuraDB Free Provisioning" (console.neo4j.io
  walkthrough) and "9. First Live Smoke Test" (3-command runbook for
  invoking the smoke test locally).

**Tests:** 17 new tests pass, 100% line coverage on `app/api/health.py`
(14 stmts) and `scripts/smoke_test.py` (37 stmts) — exceeds AC-10's 85%
target. Sprint 2a regression: 30/30 still pass. Combined: 47/47.

**Coverage pragmas:** 1 — `if __name__ == "__main__": sys.exit(main())` at
the bottom of `smoke_test.py` marked `# pragma: no cover` (the
test-driven entrypoint goes through `main()` directly; the `__main__`
guard is impossible to trigger from pytest).

**Adversarial-review note:** `kg.json()` could raise `json.JSONDecodeError`
on malformed backend response. Not caught explicitly — FastAPI always
serializes via Pydantic, so this can't happen in practice. Documented as
a known limitation; can add a broader catch in a follow-up if needed.

**Deviations from spec:**
- Spec showed monkey-patching the real `app.main` module in tests. That
  would require installing the full backend dep stack (cv2, torch,
  ultralytics, ...). The local venv only has the minimum needed for
  KG + structural work. Restructured the health test to install a
  stand-in `app.main` module via `sys.modules` and mount only the health
  router on a minimal `FastAPI()` test app. Same contract pinned;
  lighter test-time dependencies.
- The CD smoke-test step installs `httpx` directly via `pip install`
  rather than pulling it from `backend/requirements.txt`, to avoid
  having to install the whole 3-min dep set just for one CLI script.

**AC mapping:**
| AC | Covered by |
|---|---|
| AC-1 | `test_returns_200_with_required_keys` |
| AC-2 | `test_disabled_when_neo4j_uri_empty` + `test_disabled_even_when_cache_somehow_populated` |
| AC-3 | `test_ready_when_uri_set_client_present_cache_populated` |
| AC-4 | `test_error_when_uri_set_but_client_none` + `test_error_when_client_present_but_cache_empty` |
| AC-5 | `test_exits_zero_and_prints_pass` |
| AC-6 | 5 tests in `TestFailureModes` |
| AC-7 | `test_disabled_with_flag_exits_zero` |
| AC-8 | grep "Smoke-test the deployed revision" in cd.yml (1 hit) |
| AC-9 | grep "AuraDB Free Provisioning" + "First Live Smoke Test" in README (1 each) |
| AC-10 | coverage report shows 100% on both new modules; 30+17=47 tests pass |
