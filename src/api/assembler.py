"""
Tool outputs → CaseAssessment shape.

The frontend (web/lib/types.ts :: CaseAssessment) is the contract; this module
runs the three Layer 1/2 tools and reshapes their outputs into that contract.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from src.graph.connection import Neo4jConnection
from src.mcp.tools_impl import (
    detect_graph_anomalies,
    retrieve_typology_chunks,
    traverse_entity_network,
)

logger = logging.getLogger(__name__)


DEFAULT_PATTERNS: list[str] = [
    "common_controller_across_shells",
    "layered_ownership",
    "high_risk_jurisdiction",
    "shared_address_cluster",
    "intermediary_shell_network",
    "bearer_obscured_ownership",
]

_SEVERITY_SCORE = {"HIGH": 9, "MEDIUM": 6, "LOW": 3, "INFO": 1}

_FRONTEND_NODE_TYPES = {"Person", "Company", "Intermediary", "Address", "Jurisdiction"}


def build_case_assessment(
    question: str,
    node_id: str,
    entity_type: str,
    conn: Neo4jConnection,
) -> dict[str, Any]:
    traverse = traverse_entity_network(node_id, entity_type, depth=2, conn=conn)
    subgraph_rows = traverse.get("subgraph") or []
    if not subgraph_rows:
        return {"_error": f"Subject entity not found in graph: node_id={node_id}"}

    seed = subgraph_rows[0]
    # Patterns return company names in their records, not node_ids — scope by name
    # so the post-query substring filter (tools_impl.py:88-92) matches.
    scope = seed.get("entity_name") or str(node_id)
    anomalies = detect_graph_anomalies(DEFAULT_PATTERNS, entity_id=scope, conn=conn)

    chunks_payload: dict[str, Any] = {"chunks": []}
    try:
        chunks_payload = retrieve_typology_chunks(
            query_text=question or "beneficial ownership opacity shell company",
            typology_id="MAS-626",
            top_k=5,
            conn=conn,
        )
    except Exception as e:
        logger.warning("retrieve_typology_chunks unavailable: %s", e)

    findings = _build_findings(anomalies)
    typology_chunks = _build_typology_chunks(chunks_payload)
    nodes, edges = _build_subgraph(seed)
    verdict, risk_score = _score(findings)
    now = datetime.now(timezone.utc)

    return {
        "case_id": f"STR-{now:%Y-%m%d}-{str(node_id)[-4:]}",
        "subject": _build_subject(seed),
        "question": question,
        "verdict": verdict,
        "risk_score": risk_score,
        "headline": _headline(findings, seed),
        "tx_velocity": [0] * 12,  # TODO: requires Transaction nodes in Layer 1
        "findings": findings,
        "typology_chunks": typology_chunks,
        "investigation_steps": _build_steps(node_id, DEFAULT_PATTERNS, question, now),
        "subgraph": {"nodes": nodes, "edges": edges},
        "created_at": now.isoformat().replace("+00:00", "Z"),
    }


def _build_subject(seed: dict[str, Any]) -> dict[str, Any]:
    raw_type = seed.get("entity_type") or "Company"
    subject_type = "Person" if raw_type == "Person" else "Company"
    snippet_bits = [b for b in (seed.get("source_leak"), seed.get("status")) if b]
    return {
        "id": str(seed.get("entity_id") or ""),
        "name": seed.get("entity_name") or "Unknown",
        "type": subject_type,
        "jurisdiction": seed.get("jurisdiction") or "—",
        "profile_snippet": " · ".join(snippet_bits) or "No profile available.",
    }


def _build_subgraph(seed: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    seed_id = str(seed.get("entity_id") or "")
    seed_type = _normalise_type(seed.get("entity_type"))
    nodes: dict[str, dict[str, Any]] = {
        seed_id: {
            "id": seed_id,
            "label": seed.get("entity_name") or seed_id,
            "type": seed_type,
            "risk_tier": "HIGH",
        }
    }
    edges: list[dict[str, Any]] = []
    for n in seed.get("neighbours") or []:
        nid = n.get("neighbour_id")
        if nid is None:
            continue
        nid = str(nid)
        if nid not in nodes:
            nodes[nid] = {
                "id": nid,
                "label": n.get("neighbour_name") or nid,
                "type": _normalise_type(n.get("neighbour_type")),
            }
        edges.append({
            "source": seed_id,
            "target": nid,
            "kind": n.get("rel_type") or "RELATED",
        })
    return list(nodes.values()), edges


def _normalise_type(neo4j_label: str | None) -> str:
    if neo4j_label in _FRONTEND_NODE_TYPES:
        return neo4j_label  # type: ignore[return-value]
    return "Company"


def _build_findings(anomalies: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name, payload in (anomalies.get("results") or {}).items():
        if (payload.get("hits") or 0) <= 0:
            continue
        sev = payload.get("severity") or "MEDIUM"
        out.append({
            "id": f"f_{name}",
            "pattern_name": name,
            "severity": sev,
            "score": _SEVERITY_SCORE.get(sev, 5),
            "description": f"{payload.get('description', '')} ({payload['hits']} hits)",
            "evidence_ids": [],
        })
    out.sort(key=lambda f: -f["score"])
    return out


def _build_typology_chunks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for c in payload.get("chunks") or []:
        section_id = c.get("section_id") or ""
        source = "MAS Notice 626" if section_id.startswith("MAS-626") else "FATF"
        out.append({
            "id": c.get("chunk_id") or "",
            "source": source,
            "section": f"para {c.get('paragraph')}" if c.get("paragraph") else section_id,
            "title": section_id,
            "text": c.get("text") or "",
            "similarity_score": float(c.get("score") or 0.0),
        })
    return out


def _build_steps(
    node_id: str,
    patterns: list[str],
    question: str,
    now: datetime,
) -> list[dict[str, Any]]:
    def ts(offset: int) -> str:
        return (now + timedelta(seconds=offset)).isoformat().replace("+00:00", "Z")

    return [
        {
            "tool": "traverse_entity_network",
            "summary": f"Pulled 2-hop subgraph for node_id={node_id}.",
            "timestamp": ts(0),
        },
        {
            "tool": "detect_graph_anomalies",
            "summary": f"Ran {len(patterns)} patterns: {', '.join(patterns)}.",
            "timestamp": ts(1),
        },
        {
            "tool": "retrieve_typology_chunks",
            "summary": f"Vector search over MAS-626 corpus for: {question[:60] or '(default query)'}.",
            "timestamp": ts(2),
        },
    ]


def _score(findings: list[dict[str, Any]]) -> tuple[str, float]:
    # TODO(verdict-policy): replace with LLM-driven adjudication once agent loop works.
    if not findings:
        return "CLEARED", 0.0
    sevs = {f["severity"] for f in findings}
    n = len(findings)
    if "HIGH" in sevs:
        return "HIGH_RISK", round(min(0.7 + 0.05 * n, 0.95), 2)
    if "MEDIUM" in sevs:
        return "MEDIUM_RISK", round(min(0.4 + 0.05 * n, 0.7), 2)
    return "LOW_RISK", 0.2


def _headline(findings: list[dict[str, Any]], seed: dict[str, Any]) -> str:
    name = seed.get("entity_name") or "subject"
    if not findings:
        return f"No anomaly patterns hit for {name}."
    top = findings[0]
    pretty = top["pattern_name"].replace("_", " ")
    return f"{top['severity']}-severity {pretty} on {name}."
