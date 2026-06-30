"""
Smoke test for the FastAPI investigate endpoint.

Posts a question, validates that every CaseAssessment top-level key
required by web/lib/types.ts is present and well-typed, and prints a
compact summary.

Prereq: API server running on localhost:8000.
    uvicorn src.api.main:app --reload --port 8000

Usage:
    python scripts/test_api.py
"""

from __future__ import annotations

import json
import sys
from urllib import request, error

API_BASE = "http://localhost:8000"

REQUIRED_KEYS: dict[str, type] = {
    "case_id": str,
    "subject": dict,
    "question": str,
    "verdict": str,
    "risk_score": (int, float),  # type: ignore[assignment]
    "headline": str,
    "tx_velocity": list,
    "findings": list,
    "typology_chunks": list,
    "investigation_steps": list,
    "subgraph": dict,
    "created_at": str,
}

VALID_VERDICTS = {"HIGH_RISK", "MEDIUM_RISK", "LOW_RISK", "CLEARED"}


def _post(path: str, payload: dict) -> dict:
    req = request.Request(
        f"{API_BASE}{path}",
        data=json.dumps(payload).encode(),
        headers={"content-type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def _get(path: str) -> dict:
    with request.urlopen(f"{API_BASE}{path}", timeout=10) as resp:
        return json.loads(resp.read())


def main() -> int:
    print("→ GET /api/health")
    try:
        health = _get("/api/health")
    except error.URLError as e:
        print(f"  FAIL: cannot reach {API_BASE} ({e})")
        return 1
    print(f"  {health}")
    if not health.get("neo4j"):
        print("  WARN: Neo4j not reachable — /api/investigate will likely fail.")

    print("\n→ POST /api/investigate")
    try:
        case = _post(
            "/api/investigate",
            {"question": "Investigate Nielsen Enterprises beneficial ownership"},
        )
    except error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"  FAIL: HTTP {e.code} — {body}")
        return 1

    failures: list[str] = []
    for key, expected_type in REQUIRED_KEYS.items():
        if key not in case:
            failures.append(f"missing key: {key}")
            continue
        if not isinstance(case[key], expected_type):
            failures.append(
                f"key '{key}' has type {type(case[key]).__name__}, expected {expected_type}"
            )

    if case.get("verdict") not in VALID_VERDICTS:
        failures.append(f"verdict '{case.get('verdict')}' not in {VALID_VERDICTS}")

    sub = case.get("subgraph") or {}
    if not isinstance(sub.get("nodes"), list) or not isinstance(sub.get("edges"), list):
        failures.append("subgraph must have list 'nodes' and 'edges'")

    if failures:
        print("  FAIL — schema mismatches:")
        for f in failures:
            print(f"    - {f}")
        print("\nFull response:")
        print(json.dumps(case, indent=2)[:2000])
        return 1

    print("  PASS — all CaseAssessment keys present and well-typed.")
    print(
        f"\n  case_id     : {case['case_id']}"
        f"\n  subject     : {case['subject'].get('name')} ({case['subject'].get('id')}) — {case['subject'].get('jurisdiction')}"
        f"\n  verdict     : {case['verdict']} (risk_score={case['risk_score']})"
        f"\n  findings    : {len(case['findings'])} ({', '.join(f['pattern_name'] for f in case['findings'][:3])})"
        f"\n  chunks      : {len(case['typology_chunks'])}"
        f"\n  steps       : {len(case['investigation_steps'])}"
        f"\n  subgraph    : {len(sub['nodes'])} nodes / {len(sub['edges'])} edges"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
