"""Smoke-test a deployed Construction.AI backend.

Hits two endpoints and reports PASS/FAIL. Designed to be CI-friendly:
exit-0 on success, exit-1 on any failure, with a single-line summary
on the last printed line.

Usage::

    python backend/scripts/smoke_test.py --url https://example.run.app
    python backend/scripts/smoke_test.py --url https://example.run.app --allow-disabled

``--allow-disabled`` is for early-dev runs against a Cloud Run revision
deployed before Secret Manager has been populated with Aura credentials;
in that mode the backend reports ``kg_status: disabled`` and the smoke
test accepts that as PASS.
"""

from __future__ import annotations

import argparse
import sys

import httpx

ROOT_TIMEOUT_S = 10.0
KG_TIMEOUT_S = 10.0


def smoke_test(url: str, allow_disabled: bool = False) -> int:
    """Return 0 on PASS, 1 on FAIL. Prints a single summary line last."""
    base = url.rstrip("/")

    try:
        root = httpx.get(f"{base}/", timeout=ROOT_TIMEOUT_S)
        if root.status_code != 200:
            print(f"FAIL: GET / returned {root.status_code}")
            return 1

        kg = httpx.get(f"{base}/api/health/kg", timeout=KG_TIMEOUT_S)
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke-test the deployed backend.")
    parser.add_argument(
        "--url",
        required=True,
        help="Base URL of the backend service (e.g. https://construction-ai-backend-xxx.run.app)",
    )
    parser.add_argument(
        "--allow-disabled",
        action="store_true",
        help="Treat kg_status='disabled' as PASS (early-dev posture without Aura).",
    )
    args = parser.parse_args(argv)
    return smoke_test(args.url, allow_disabled=args.allow_disabled)


if __name__ == "__main__":  # pragma: no cover - thin CLI dispatch
    sys.exit(main())
