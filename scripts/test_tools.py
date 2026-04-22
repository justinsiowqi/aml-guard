"""
Direct test of the three custom MCP tools — no LLM involved.

Calls each tool's Python implementation against the live Neo4j graph
(via the HTTPS Query API v2) and prints a summary of what came back.

Run from the project root:
    python scripts/test_tools.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv()

from src.graph.connection import Neo4jConnection
from src.mcp.tools_impl import (
    detect_graph_anomalies,
    retrieve_typology_chunks,
    traverse_entity_network,
)

# ─────────────────────────────────────────────────────────────────────────────
# Test inputs — edit these as the dataset evolves
# ─────────────────────────────────────────────────────────────────────────────

# traverse_entity_network
ENTITY_ID   = "Mossack Fonseca & Co."   # name or node_id
ENTITY_TYPE = "Intermediary"             # Person | Company | Intermediary
DEPTH       = 2

# detect_graph_anomalies
PATTERN_NAMES = [
    "common_controller_across_shells",
    "high_risk_jurisdiction",
    "intermediary_shell_network",
]
SCOPE_ENTITY_ID = None   # or e.g. "Mossack Fonseca & Co." to scope results

# retrieve_typology_chunks
QUERY_TEXT  = "beneficial ownership disclosure and customer due diligence"
TYPOLOGY_ID = None       # or "MAS-626"
TOP_K       = 3


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _section(title: str) -> None:
    bar = "─" * 70
    print(f"\n{bar}\n {title}\n{bar}")


def _summarise(result: dict, max_rows: int = 3) -> None:
    """Print a compact view of a tool result so the terminal stays readable."""
    if "error" in result:
        print(f"  ERROR: {result['error']}")
        return

    for key, value in result.items():
        if isinstance(value, list):
            print(f"  {key}: ({len(value)} items)")
            for row in value[:max_rows]:
                print(f"    - {json.dumps(row, default=str)[:200]}")
            if len(value) > max_rows:
                print(f"    … (+{len(value) - max_rows} more)")
        elif isinstance(value, dict):
            print(f"  {key}:")
            for k, v in list(value.items())[:max_rows]:
                snippet = json.dumps(v, default=str)[:200]
                print(f"    {k}: {snippet}")
            if len(value) > max_rows:
                print(f"    … (+{len(value) - max_rows} more)")
        else:
            print(f"  {key}: {value}")


# ─────────────────────────────────────────────────────────────────────────────
# Run
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    with Neo4jConnection() as conn:

        _section(f"1. traverse_entity_network  ({ENTITY_TYPE}: {ENTITY_ID})")
        result = traverse_entity_network(
            entity_id=ENTITY_ID,
            entity_type=ENTITY_TYPE,
            depth=DEPTH,
            conn=conn,
        )
        _summarise(result)

        _section(f"2. detect_graph_anomalies  ({len(PATTERN_NAMES)} patterns)")
        result = detect_graph_anomalies(
            pattern_names=PATTERN_NAMES,
            entity_id=SCOPE_ENTITY_ID,
            conn=conn,
        )
        print(f"  patterns_run: {result.get('patterns_run')}")
        for name, payload in result.get("results", {}).items():
            print(
                f"\n  [{name}] severity={payload['severity']} "
                f"hits={payload['hits']}"
            )
            for row in payload.get("records", [])[:2]:
                print(f"    - {json.dumps(row, default=str)[:200]}")
            if "error" in payload:
                print(f"    ERROR: {payload['error']}")

        _section(f"3. retrieve_typology_chunks  (query='{QUERY_TEXT[:50]}…')")
        result = retrieve_typology_chunks(
            query_text=QUERY_TEXT,
            typology_id=TYPOLOGY_ID,
            top_k=TOP_K,
            conn=conn,
        )
        print(f"  query: {result.get('query')}")
        for chunk in result.get("chunks", []):
            print(
                f"\n    chunk_id={chunk['chunk_id']}  "
                f"paragraph={chunk['paragraph']}  "
                f"score={chunk['score']:.3f}"
            )
            print(f"    text: {chunk['text'][:200]}…")

    print("\n✔ Done — all three tools executed.")


if __name__ == "__main__":
    main()
