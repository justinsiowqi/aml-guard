"""
Tool outputs → CaseAssessment shape.

The frontend (web/lib/types.ts :: CaseAssessment) is the contract; this module
runs the three Layer 1/2 tools and reshapes their outputs into that contract.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from src.graph.connection import Neo4jConnection
from src.graph.queries import get_full_paragraph_text
from src.mcp.schema import ANOMALY_REGISTRY
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

_SENTENCE_TERMINATOR = re.compile(r"[.!?]\s")
_SNIPPET_MAX_CHARS = 350

# Matches chunks that are only a bracketed metadata header (e.g. document
# amendment markers like "[MAS Notice 626 (Amendment) 2025]") — these get
# embedded by the ingestion pipeline and rank highly against short queries.
_JUNK_CHUNK_RE = re.compile(r"^\s*\[[^\]]*\]\s*$")


def _is_junk_chunk(text: str) -> bool:
    if not text:
        return True
    return bool(_JUNK_CHUNK_RE.match(text))


def _cap_to_sentence(text: str, max_chars: int = _SNIPPET_MAX_CHARS) -> str:
    """Truncate text to <=max_chars, rounded down to a sentence terminator."""
    if len(text) <= max_chars:
        return text
    last_term = None
    for m in _SENTENCE_TERMINATOR.finditer(text[: max_chars + 50]):
        last_term = m.end()
    if last_term is not None and last_term <= max_chars + 50:
        return text[:last_term].strip()
    return text[:max_chars].rstrip() + "…"


def _trim_to_sentence_window(
    full_paragraph: str,
    matched_text: str,
    max_chars: int = _SNIPPET_MAX_CHARS,
) -> str:
    """
    Anchor matched_text within full_paragraph, start at the sentence
    boundary before it, and return a snippet of at most ~max_chars that
    ends at the last sentence terminator within range. Falls back to a
    capped version of matched_text if the anchor can't be located.
    """
    matched_clean = (matched_text or "").strip()
    if not matched_clean or not full_paragraph:
        return _cap_to_sentence(matched_clean or full_paragraph, max_chars)

    needle = matched_clean[:40]
    pos = full_paragraph.find(needle)
    if pos < 0:
        return _cap_to_sentence(matched_clean, max_chars)

    # Backward: start of the sentence containing pos
    start = 0
    for m in _SENTENCE_TERMINATOR.finditer(full_paragraph[:pos]):
        start = m.end()

    # Forward: cap at start + max_chars, rounding back to last sentence terminator
    soft_end = min(start + max_chars, len(full_paragraph))
    last_term = None
    for m in _SENTENCE_TERMINATOR.finditer(full_paragraph, start, soft_end + 1):
        last_term = m.end()
    end = last_term if last_term is not None else soft_end

    snippet = full_paragraph[start:end].strip()
    if last_term is None and end < len(full_paragraph):
        snippet = snippet + "…"
    return snippet


def expand_chunks_to_paragraphs(
    raw_chunks: list[dict[str, Any]],
    conn: Neo4jConnection,
    *,
    dedupe: bool = True,
) -> list[dict[str, Any]]:
    """
    For each matched chunk, fetch the full paragraph it belongs to and
    return a sentence-bounded snippet around the match. Fixes the
    embedding-fragment problem (mid-word starts) without dragging in the
    entire paragraph.

    When dedupe=True, collapses multiple matched chunks of the same
    paragraph to one entry, keeping the highest-scoring chunk_id.
    """
    if not raw_chunks:
        return []

    raw_chunks = [c for c in raw_chunks if not _is_junk_chunk(c.get("text") or "")]

    if dedupe:
        by_para: dict[tuple[str, str], dict[str, Any]] = {}
        for c in raw_chunks:
            key = (c.get("section_id") or "", c.get("paragraph") or "")
            existing = by_para.get(key)
            if existing is None or (c.get("score") or 0) > (existing.get("score") or 0):
                by_para[key] = c
        unique = list(by_para.values())
    else:
        unique = list(raw_chunks)

    unique.sort(key=lambda c: -(c.get("score") or 0))

    expanded: list[dict[str, Any]] = []
    for c in unique:
        section_id = c.get("section_id") or ""
        paragraph = c.get("paragraph") or ""
        original_text = c.get("text") or ""
        if not section_id or not paragraph:
            expanded.append(c)
            continue
        try:
            full = get_full_paragraph_text(conn, section_id, paragraph)
        except Exception as e:
            logger.warning(
                "get_full_paragraph_text failed for %s para %s: %s",
                section_id, paragraph, e,
            )
            full = ""
        snippet = _trim_to_sentence_window(full, original_text) if full else original_text
        if _is_junk_chunk(snippet):
            continue
        # Keep the full paragraph alongside so the UI can offer a "Show more"
        # expansion when the snippet was truncated.
        expanded.append({**c, "text": snippet, "text_full": full or snippet})
    return expanded


def shape_chunk(c: dict[str, Any]) -> dict[str, Any] | None:
    """Map a raw retrieve_typology_chunks chunk dict to the frontend TypologyChunk shape."""
    chunk_id = c.get("chunk_id")
    if not chunk_id:
        return None
    section_id = c.get("section_id") or ""
    source = "MAS Notice 626" if section_id.startswith("MAS-626") else "FATF"
    text = c.get("text") or ""
    text_full = c.get("text_full") or text
    return {
        "id": chunk_id,
        "source": source,
        "section": f"para {c.get('paragraph')}" if c.get("paragraph") else section_id,
        "title": section_id,
        "text": text,
        "text_full": text_full,
        "similarity_score": float(c.get("score") or 0.0),
    }

# ICIJ corporate-registry status codes are raw legal/registry states. "Changed
# agent" in particular collides with our AI-agent vocabulary in the UI; remap
# to clearer phrasing before showing it in the subject header.
_STATUS_LABELS: dict[str, str] = {
    "Changed agent": "Changed registrar",
    "Bad debt account": "Bad debt",
    "In transition": "Restructuring",
    "Relocated in new jurisdiction": "Relocated jurisdiction",
}


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

    findings = _build_findings(anomalies)
    typology_chunks = _attach_evidence(findings, question, conn)
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
    status_raw = seed.get("status")
    status = _STATUS_LABELS.get(status_raw, status_raw) if status_raw else None
    snippet_bits = [b for b in (seed.get("source_leak"), status) if b]
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


def _attach_evidence(
    findings: list[dict[str, Any]],
    question: str,
    conn: Neo4jConnection,
) -> list[dict[str, Any]]:
    """
    Run a vector search per fired finding using the pattern's own description as
    the query. Populate each finding's evidence_ids with the retrieved chunk_ids
    and return a deduped global typology_chunks list. If no findings fire, fall
    back to one query-based search so the UI still has some regulatory context.
    """
    chunks_by_id: dict[str, dict[str, Any]] = {}

    targets: list[tuple[dict[str, Any] | None, str]] = []
    if findings:
        for f in findings:
            pat = ANOMALY_REGISTRY.get(f["pattern_name"])
            if pat is None:
                continue
            targets.append((f, pat.description))
    else:
        targets.append((None, question or "beneficial ownership opacity shell company"))

    for finding, query_text in targets:
        try:
            payload = retrieve_typology_chunks(
                query_text=query_text,
                typology_id="MAS-626",
                top_k=2,
                conn=conn,
            )
        except Exception as e:
            logger.warning("retrieve_typology_chunks failed for '%s': %s", query_text[:60], e)
            continue

        finding_chunk_ids: list[str] = []
        expanded = expand_chunks_to_paragraphs(payload.get("chunks") or [], conn, dedupe=True)
        for c in expanded:
            shaped = shape_chunk(c)
            if shaped is None:
                continue
            chunk_id = shaped["id"]
            chunks_by_id.setdefault(chunk_id, shaped)
            finding_chunk_ids.append(chunk_id)

        if finding is not None:
            finding["evidence_ids"] = finding_chunk_ids

    return list(chunks_by_id.values())


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
            "summary": "Vector search over MAS-626 driven by pattern descriptions of each finding.",
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
