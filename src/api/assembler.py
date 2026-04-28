"""
Tool outputs → CaseAssessment shape.

The frontend (web/lib/types.ts :: CaseAssessment) is the contract; this module
runs the three Layer 1/2 tools and reshapes their outputs into that contract.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from src.graph.connection import Neo4jConnection
from src.graph.queries import get_entity_subgraph_2hop, get_full_paragraph_text
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
# Clause-level split: include `;` because regulatory text uses semicolons to
# separate enumerated sub-clauses that read as independent units.
_CLAUSE_SPLIT = re.compile(r"(?<=[.!?;])\s+")
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


def _top_matching_sentences(
    paragraph: str,
    query: str,
    top_n: int = 2,
) -> list[str]:
    """
    Split paragraph into sentence/clause-level units and return up to top_n
    that best match the query. Uses 4-char stem substring matching so
    "structured" and "structuring" both hit on stem "stru". Sentences are
    returned in their original paragraph order to preserve flow. Falls back
    to the first top_n clauses if no query terms overlap.
    """
    sentences = [s.strip() for s in _CLAUSE_SPLIT.split(paragraph) if s.strip()]
    if not sentences:
        return []

    query_stems = {w.lower()[:4] for w in re.findall(r"[a-zA-Z]{4,}", query)}
    if not query_stems:
        return sentences[:top_n]

    scored: list[tuple[int, int, str]] = []
    for i, s in enumerate(sentences):
        s_lower = s.lower()
        hits = sum(1 for stem in query_stems if stem in s_lower)
        scored.append((hits, i, s))

    if all(h == 0 for h, _, _ in scored):
        return sentences[:top_n]

    top = sorted(scored, key=lambda x: -x[0])[:top_n]
    top.sort(key=lambda x: x[1])
    return [s for _, _, s in top]


def expand_chunks_to_paragraphs(
    raw_chunks: list[dict[str, Any]],
    conn: Neo4jConnection,
    query: str,
    *,
    dedupe: bool = True,
) -> list[dict[str, Any]]:
    """
    For each matched chunk, fetch the full paragraph and extract the
    sentences that best match `query`. Returns:
      - text:      those sentences capped at SNIPPET_MAX_CHARS
      - text_full: those same sentences untruncated

    "Show more" in the UI swaps text → text_full so the user sees the
    matched sentences in full, never the entire paragraph.

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

        if full:
            top_sents = _top_matching_sentences(full, query, top_n=2)
            text_full = " ".join(top_sents).strip() or original_text
        else:
            text_full = original_text

        snippet = _cap_to_sentence(text_full, _SNIPPET_MAX_CHARS)
        if _is_junk_chunk(snippet):
            continue

        expanded.append({**c, "text": snippet, "text_full": text_full})
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

# Maps each anomaly pattern to a high-level risk category for the verdict
# decomposition bars. Categories cover the patterns we actually run in
# DEFAULT_PATTERNS so each bar has a chance of firing.
_PATTERN_CATEGORIES: list[tuple[str, list[str]]] = [
    ("Ownership Opacity", [
        "layered_ownership",
        "common_controller_across_shells",
        "bearer_obscured_ownership",
    ]),
    ("Jurisdiction",       ["high_risk_jurisdiction"]),
    ("Intermediary",       ["intermediary_shell_network"]),
    ("Address Clustering", ["shared_address_cluster"]),
]

# Floor so empty categories don't render as a flat bar.
_DECOMP_FLOOR = 0.05

# Human-readable labels for raw Neo4j relationship types.
_KIND_LABELS: dict[str, str] = {
    "INTERMEDIARY_OF":     "Intermediary of",
    "IS_OFFICER_OF":       "Officer of",
    "REGISTERED_AT":       "Registered at",
    "INCORPORATED_IN":     "Incorporated in",
    "SHARES_ADDRESS_WITH": "Shares address with",
    "RECEIVED_WIRE_FROM":  "Received wire from",
    "ROUTED_THROUGH":      "Routed through",
}

# Counterparty type ordering for connection-focus selection.
_FOCUS_TYPE_PRIORITY = {
    "Intermediary": 0,
    "Person":       1,
    "Company":      2,
    "Address":      3,
    "Jurisdiction": 4,
}


def _humanize_kind(kind: str) -> str:
    return _KIND_LABELS.get(kind, kind.replace("_", " ").lower().capitalize())


def _smart_address_label(raw: str | None) -> str | None:
    """
    ICIJ Address.address fields concatenate the registrant name + full postal
    address, joined by ';'. Truncated they collide with the Intermediary
    node's label. Use the last segment (country/region) — short and locative.
    """
    if not raw:
        return raw
    parts = [p.strip() for p in raw.split(";") if p.strip()]
    return parts[-1] if len(parts) >= 2 else raw


def _build_risk_decomposition(
    findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    For each named risk category, take the maximum normalized severity across
    fired patterns in that category. Empty categories floor at _DECOMP_FLOOR
    so bars don't fully collapse.
    """
    by_pattern: dict[str, int] = {f["pattern_name"]: f["score"] for f in findings}
    out: list[dict[str, Any]] = []
    for label, patterns in _PATTERN_CATEGORIES:
        scores = [by_pattern[p] for p in patterns if p in by_pattern]
        value = max(scores) / 9 if scores else _DECOMP_FLOOR
        out.append({"label": label, "value": round(value, 2)})
    return out


def _synth_tx_velocity(case_id: str) -> list[int]:
    """
    Deterministic 12-month transaction-volume fingerprint from case_id.
    Baseline 0–5 with a 1–2 month spike (18–29 → 10–17 echo). Synthetic;
    used until real Transaction nodes exist in Layer 1.
    """
    h = hashlib.md5(case_id.encode()).digest()
    base = [h[i] % 6 for i in range(12)]
    spike = h[12] % 12
    base[spike] = 18 + (h[13] % 12)
    if spike + 1 < 12:
        base[spike + 1] = 10 + (h[14] % 8)
    return base


def _build_connection_focus(
    seed_id: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """
    Pick the most interesting non-seed counterparty for the focus card. All
    facts come from graph data — no fabricated dollar amounts.
    """
    by_id = {n["id"]: n for n in nodes if n["id"] != seed_id}
    if not by_id:
        return None

    edge_kinds: dict[str, list[str]] = {}
    for e in edges:
        if e["source"] == seed_id and e["target"] in by_id:
            edge_kinds.setdefault(e["target"], []).append(e["kind"])
        elif e["target"] == seed_id and e["source"] in by_id:
            edge_kinds.setdefault(e["source"], []).append(e["kind"])

    candidates = [by_id[cid] for cid in edge_kinds]
    if not candidates:
        return None

    candidates.sort(key=lambda n: (
        _FOCUS_TYPE_PRIORITY.get(n["type"], 99),
        n.get("label", ""),
    ))
    focus = candidates[0]
    kinds = edge_kinds.get(focus["id"], [])
    rel_summary = ", ".join(sorted({_humanize_kind(k) for k in kinds}))

    return {
        "counterparty_label":   focus.get("label", focus["id"]),
        "counterparty_type":    focus["type"],
        "risk_tier":            focus.get("risk_tier") or "MEDIUM",
        "relationship_summary": rel_summary or "Connected",
        "link_count":           len(kinds),
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
    # Patterns return rows scoped to the seed's *context* — sometimes the seed
    # name itself (common_controller_across_shells), sometimes an intermediary
    # name (intermediary_shell_network), sometimes a jurisdiction
    # (high_risk_jurisdiction). Pass all of them so the substring filter in
    # detect_graph_anomalies doesn't drop legitimate hits.
    scope_terms: list[str] = []
    if seed.get("entity_name"):
        scope_terms.append(seed["entity_name"])
    else:
        scope_terms.append(str(node_id))
    for n in seed.get("neighbours") or []:
        nm = n.get("neighbour_name")
        if nm:
            scope_terms.append(nm)
    if seed.get("jurisdiction"):
        scope_terms.append(seed["jurisdiction"])
    anomalies = detect_graph_anomalies(DEFAULT_PATTERNS, entity_id=scope_terms, conn=conn)

    findings = _build_findings(anomalies)
    typology_chunks = _attach_evidence(findings, question, conn)

    try:
        two_hop_rows = get_entity_subgraph_2hop(conn, str(node_id))
    except Exception as e:
        logger.warning("get_entity_subgraph_2hop failed for %s: %s", node_id, e)
        two_hop_rows = []

    nodes, edges = _build_subgraph(seed, two_hop_rows)
    verdict, risk_score = _score(findings)
    now = datetime.now(timezone.utc)
    case_id = f"STR-{now:%Y-%m%d}-{str(node_id)[-4:]}"
    seed_id = str(seed.get("entity_id") or "")

    return {
        "case_id": case_id,
        "subject": _build_subject(seed),
        "question": question,
        "verdict": verdict,
        "risk_score": risk_score,
        "headline": _headline(findings, seed),
        "tx_velocity": _synth_tx_velocity(case_id),
        "risk_decomposition": _build_risk_decomposition(findings),
        "connection_focus": _build_connection_focus(seed_id, nodes, edges),
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


def _build_subgraph(
    seed: dict[str, Any],
    two_hop_rows: list[dict[str, Any]] | None = None,
    *,
    max_2hop_nodes: int = 8,
) -> tuple[list[dict], list[dict]]:
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
    one_hop_ids: set[str] = set()

    # 1-hop tier — direct neighbours of the seed.
    for n in seed.get("neighbours") or []:
        nid = n.get("neighbour_id")
        if nid is None:
            continue
        nid = str(nid)
        one_hop_ids.add(nid)
        if nid not in nodes:
            ntype = _normalise_type(n.get("neighbour_type"))
            label = n.get("neighbour_name") or nid
            if ntype == "Address":
                label = _smart_address_label(label) or label
            nodes[nid] = {
                "id": nid,
                "label": label,
                "type": ntype,
            }
        edges.append({
            "source": seed_id,
            "target": nid,
            "kind": n.get("rel_type") or "RELATED",
        })

    # 2-hop tier — extensions hanging off each 1-hop neighbour. Cap to keep
    # the outer ring readable; once we hit the cap, accept further edges
    # only when they connect to already-included 2-hop nodes.
    two_hop_added = 0
    for r in two_hop_rows or []:
        h1 = r.get("hop1_id")
        h2 = r.get("hop2_id")
        if h1 is None or h2 is None:
            continue
        h1, h2 = str(h1), str(h2)
        if h1 not in one_hop_ids or h2 == seed_id or h2 in one_hop_ids:
            continue
        if h2 not in nodes:
            if two_hop_added >= max_2hop_nodes:
                continue
            h2_type = _normalise_type(r.get("hop2_type"))
            h2_label = r.get("hop2_name") or h2
            if h2_type == "Address":
                h2_label = _smart_address_label(h2_label) or h2_label
            nodes[h2] = {
                "id": h2,
                "label": h2_label,
                "type": h2_type,
            }
            two_hop_added += 1
        edges.append({
            "source": h1,
            "target": h2,
            "kind": r.get("hop2_rel") or "RELATED",
        })

    # Dedupe edges by (source, target, kind) — 2-hop traversal can revisit
    # the same pair via multiple paths.
    seen: set[tuple[str, str, str]] = set()
    unique_edges: list[dict[str, Any]] = []
    for e in edges:
        key = (e["source"], e["target"], e["kind"])
        if key in seen:
            continue
        seen.add(key)
        unique_edges.append(e)

    return list(nodes.values()), unique_edges


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
        expanded = expand_chunks_to_paragraphs(
            payload.get("chunks") or [], conn, query_text, dedupe=True,
        )
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
