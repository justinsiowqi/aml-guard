"""Plain Python implementations of all AML Guard MCP tools."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.graph.connection import Neo4jConnection

logger = logging.getLogger(__name__)

# Resolve helper modules for both dev mode (src.*) and bundled mode (aml_tools.*).
try:
    from src.graph.queries import (
        get_entity_subgraph,
        get_entity_network,
        get_intermediary_network,
        vector_search_typology_chunks,
    )
    from src.mcp.schema import ANOMALY_REGISTRY
    from src.agent.config import EMBEDDING_MODEL
except ImportError:
    from aml_tools.queries import (
        get_entity_subgraph,
        get_entity_network,
        get_intermediary_network,
        vector_search_typology_chunks,
    )
    from aml_tools.schema import ANOMALY_REGISTRY
    EMBEDDING_MODEL = "bge-large-en-v1.5"


def traverse_entity_network(
    entity_id: str,
    entity_type: str,
    depth: int = 2,
    conn: "Neo4jConnection | None" = None,
) -> dict:
    """
    Pull entity subgraph and ownership/association network for a Layer 1 entity.

    For Intermediary entities, also returns the full intermediary network
    (all companies set up and their jurisdictions).
    """
    subgraph = get_entity_subgraph(conn, entity_id)
    network  = get_entity_network(conn, entity_id, depth)

    result = {
        "entity_id":   entity_id,
        "entity_type": entity_type,
        "subgraph":    subgraph,
        "network":     network,
    }

    if entity_type == "Intermediary":
        result["intermediary_network"] = get_intermediary_network(conn, entity_id)

    return result


def detect_graph_anomalies(
    pattern_names: list[str],
    entity_id: str | list[str] | None = None,
    conn: "Neo4jConnection | None" = None,
) -> dict:
    """
    Run named anomaly patterns from ANOMALY_REGISTRY against the graph.

    If entity_id is provided, filters each result set to rows where any
    string field contains any of the supplied terms. Pass a list to widen
    scope to e.g. seed + 1-hop neighbour names + jurisdiction so patterns
    that report on the seed's *context* (intermediaries, jurisdictions)
    aren't dropped because they don't repeat the seed's name.
    """
    unknown = [n for n in pattern_names if n not in ANOMALY_REGISTRY]
    if unknown:
        logger.warning("Unknown pattern names requested: %s", unknown)

    if isinstance(entity_id, str):
        scope_terms = [entity_id] if entity_id else []
    else:
        scope_terms = [t for t in (entity_id or []) if t]

    results = {}
    for name in pattern_names:
        pat = ANOMALY_REGISTRY.get(name)
        if pat is None:
            continue
        try:
            rows = conn.run_query(pat.cypher, pat.params or {})

            if scope_terms and rows:
                rows = [
                    r for r in rows
                    if any(t in str(v) for t in scope_terms for v in r.values())
                ]

            results[name] = {
                "hits":        len(rows),
                "severity":    pat.severity,
                "description": pat.description,
                "records":     rows,
            }
        except Exception as e:
            logger.error("Pattern %s failed: %s", name, e)
            results[name] = {
                "hits":        0,
                "severity":    pat.severity,
                "description": pat.description,
                "records":     [],
                "error":       str(e),
            }

    return {
        "patterns_run": list(results.keys()),
        "results":      results,
    }


def retrieve_typology_chunks(
    query_text: str,
    typology_id: str | None = None,
    top_k: int = 5,
    conn: "Neo4jConnection | None" = None,
) -> dict:
    """
    Embed query_text via H2OGPTe and run vector search over Layer 2 chunks.

    Returns:
        {
          "query": str,
          "chunks": [
            {"chunk_id": str, "text": str, "paragraph": str, "section_id": str, "score": float},
            ...
          ]
        }
    """
    from h2ogpte import H2OGPTE

    h2ogpte_url = os.getenv("H2OGPTE_URL") or os.getenv("H2OGPTE_ADDRESS")
    h2ogpte_key = os.getenv("H2OGPTE_API_KEY")
    if not h2ogpte_url or not h2ogpte_key:
        raise RuntimeError("H2OGPTE_URL (or H2OGPTE_ADDRESS) and H2OGPTE_API_KEY must be set.")

    client = H2OGPTE(address=h2ogpte_url, api_key=h2ogpte_key)
    embedding = client.encode_for_retrieval(
        chunks=[query_text],
        embedding_model=EMBEDDING_MODEL,
    )[0]

    rows = vector_search_typology_chunks(conn, embedding, typology_id, top_k)

    return {
        "query": query_text,
        "chunks": [
            {
                "chunk_id":  r["chunk_id"],
                "text":      r["text"],
                "paragraph": r["paragraph"],
                "section_id": r["section_id"],
                "score":     r["score"],
            }
            for r in rows
        ],
    }


