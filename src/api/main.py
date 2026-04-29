"""
FastAPI HTTP layer for the Next.js frontend.

Run from the project root:

    uvicorn src.api.main:app --reload --port 8000

The frontend (web/lib/api.ts) posts to ${NEXT_PUBLIC_API_BASE}/api/investigate
and expects a CaseAssessment-shaped response (see web/lib/types.ts).
"""

from __future__ import annotations

import logging
import re
from threading import Lock

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.agent.aml_agent import AMLAgent
from src.api.assembler import (
    build_case_assessment,
    expand_chunks_to_paragraphs,
    shape_chunk,
)
from src.api.merge import merge_agent_into_case
from src.api.narrator import enrich_with_narrative
from src.graph.connection import Neo4jConnection
from src.mcp.tools_impl import (
    detect_graph_anomalies,
    retrieve_typology_chunks,
    traverse_entity_network,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="AML Guard API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://localhost:3000"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["content-type"],
    allow_credentials=False,
)


NIELSEN_NODE_ID = "10122953"
NIELSEN_TYPE = "Company"

# Words that look like Title-Case nouns but should never be matched as entity names.
_RESOLVE_STOP = {
    "investigate", "investigation", "analyse", "analyze", "review", "check", "audit",
    "look", "show", "find", "tell", "give", "run", "see", "get", "do", "make",
    "what", "who", "why", "when", "where", "how", "is", "are", "was", "were",
    "structuring", "layering", "laundering", "money", "risk", "shell", "beneficial",
    "ownership", "sanctions", "pep", "politically", "exposed", "person", "company",
    "entity", "the", "for", "and", "of", "in", "on", "with", "from", "to", "this",
    "that", "their", "his", "her", "any", "all", "some", "at",
}

_RESOLVE_CYPHER = """
WITH $candidate AS q, toLower($candidate) AS qlow
MATCH (c:Company)
WHERE toLower(c.name) = qlow
   OR toLower(coalesce(c.original_name, '')) = qlow
   OR toLower(coalesce(c.former_name, '')) = qlow
   OR toLower(c.name) CONTAINS qlow
   OR (size(qlow) >= 4 AND toLower(coalesce(c.original_name, '')) CONTAINS qlow)
   OR (size(qlow) >= 4 AND toLower(coalesce(c.former_name, '')) CONTAINS qlow)
RETURN c.node_id AS node_id, c.name AS name,
  CASE
    WHEN toLower(c.name) = qlow THEN 1.0
    WHEN toLower(coalesce(c.original_name, '')) = qlow THEN 0.95
    WHEN toLower(coalesce(c.former_name, '')) = qlow THEN 0.9
    ELSE toFloat(size(qlow)) / toFloat(size(c.name))
  END AS score
ORDER BY score DESC
LIMIT 1
"""


def _extract_candidates(question: str) -> list[str]:
    """Pull plausible Title-Case noun-phrase candidates from the question.

    Examples:
        "Investigate Nielsen Enterprises for structuring" -> ["Nielsen Enterprises"]
        "Look at Mossack Fonseca and BSI"                 -> ["Mossack Fonseca", "BSI"]
        "investigate structuring risk"                    -> []
    """
    matches = re.findall(
        r"[A-Z][a-zA-Z&.'\-]{2,}(?:\s+[A-Z][a-zA-Z&.'\-]{1,}){0,4}",
        question,
    )
    cleaned: list[str] = []
    for m in matches:
        # Strip stop-words from edges (e.g. "Investigate Nielsen" -> "Nielsen").
        words = [w for w in m.split() if w.lower() not in _RESOLVE_STOP]
        if not words:
            continue
        candidate = " ".join(words).strip()
        if len(candidate) >= 3 and candidate not in cleaned:
            cleaned.append(candidate)
    return cleaned


def resolve_entity(question: str) -> tuple[str, str]:
    """Fuzzy-match a Company name from the question against Neo4j.

    Falls back to the Nielsen seed when no candidate scores >= 0.6, when no
    candidates can be extracted, or when the Cypher round-trip fails. Always
    returns a valid (node_id, type) tuple — never raises.
    """
    candidates = _extract_candidates(question)
    if not candidates:
        logger.info("resolve_entity: no candidates extracted; using Nielsen seed.")
        return (NIELSEN_NODE_ID, NIELSEN_TYPE)
    try:
        with Neo4jConnection() as conn:
            for cand in candidates:
                rows = conn.run_query(_RESOLVE_CYPHER, {"candidate": cand})
                if rows and rows[0].get("score", 0.0) >= 0.6:
                    nid = str(rows[0]["node_id"])
                    logger.info(
                        "resolve_entity: '%s' -> %s (node_id=%s, score=%.2f)",
                        cand, rows[0].get("name"), nid, rows[0]["score"],
                    )
                    return (nid, "Company")
    except Exception as e:
        logger.warning("resolve_entity Cypher failed (%s); using Nielsen seed.", e)
        return (NIELSEN_NODE_ID, NIELSEN_TYPE)
    logger.info(
        "resolve_entity: no match >=0.6 across %d candidate(s); using Nielsen seed.",
        len(candidates),
    )
    return (NIELSEN_NODE_ID, NIELSEN_TYPE)


# ─────────────────────────────────────────────────────────────────────────────
# Request models
# ─────────────────────────────────────────────────────────────────────────────


class InvestigateRequest(BaseModel):
    question: str


class TraverseRequest(BaseModel):
    entity_id: str
    entity_type: str
    depth: int = 2


class AnomaliesRequest(BaseModel):
    pattern_names: list[str]
    entity_id: str | None = None


class ChunksRequest(BaseModel):
    query_text: str
    typology_id: str | None = None
    top_k: int = 5


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@app.get("/api/health")
def health() -> dict:
    try:
        with Neo4jConnection() as conn:
            conn.run_query("RETURN 1 AS ok", {})
        return {"status": "ok", "neo4j": True}
    except Exception as e:
        logger.warning("Neo4j health probe failed: %s", e)
        return {"status": "degraded", "neo4j": False, "error": str(e)}


def _connect() -> Neo4jConnection:
    try:
        return Neo4jConnection().__enter__()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"Neo4j unavailable: {e}") from e


@app.post("/api/investigate")
def investigate(req: InvestigateRequest) -> dict:
    node_id, entity_type = resolve_entity(req.question)
    conn = _connect()
    try:
        result = build_case_assessment(req.question, node_id, entity_type, conn)
    finally:
        conn.close()
    if "_error" in result:
        raise HTTPException(status_code=404, detail=result["_error"])
    return enrich_with_narrative(result)


# Lazy singleton — AMLAgent.setup() creates an H2OGPTe collection and registers
# MCP tools. Both are expensive; do it once per process behind a lock.
_AGENT_LOCK = Lock()
_AGENT_SINGLETON: AMLAgent | None = None


def _get_agent() -> AMLAgent:
    global _AGENT_SINGLETON
    with _AGENT_LOCK:
        if _AGENT_SINGLETON is None:
            agent = AMLAgent()
            agent.setup()
            _AGENT_SINGLETON = agent
        return _AGENT_SINGLETON


@app.post("/api/investigate/deep")
def investigate_deep(req: InvestigateRequest) -> dict:
    """Run the full H2OGPTe agent loop on top of the deterministic trunk.

    The deterministic case is built first (we need its subgraph, findings,
    typology_chunks, and evidence_ids regardless). Then the agent runs and
    its verdict / summary / recommended_actions are merged in. Latency is
    30-90s on first call due to collection setup + tool registration.
    """
    node_id, entity_type = resolve_entity(req.question)
    conn = _connect()
    try:
        case = build_case_assessment(req.question, node_id, entity_type, conn)
    finally:
        conn.close()
    if "_error" in case:
        raise HTTPException(status_code=404, detail=case["_error"])

    try:
        agent_resp = _get_agent().run(req.question)
    except Exception as e:
        logger.exception("Deep-analysis agent failed")
        raise HTTPException(status_code=502, detail=f"Agent unavailable: {e}") from e

    return merge_agent_into_case(case, agent_resp)


@app.post("/api/traverse")
def traverse(req: TraverseRequest) -> dict:
    conn = _connect()
    try:
        return traverse_entity_network(req.entity_id, req.entity_type, req.depth, conn=conn)
    finally:
        conn.close()


@app.post("/api/anomalies")
def anomalies(req: AnomaliesRequest) -> dict:
    conn = _connect()
    try:
        return detect_graph_anomalies(req.pattern_names, entity_id=req.entity_id, conn=conn)
    finally:
        conn.close()


@app.post("/api/chunks")
def chunks(req: ChunksRequest) -> dict:
    """Free-form vector search over the regulatory corpus.

    Returns chunks pre-shaped to match the frontend TypologyChunk type
    (web/lib/types.ts), so the Citation Viewer can render them directly.
    """
    conn = _connect()
    try:
        # Pull a few extra so post-dedup we still have ~top_k results.
        payload = retrieve_typology_chunks(
            req.query_text,
            typology_id=req.typology_id or "MAS-626",
            top_k=req.top_k * 2,
            conn=conn,
        )
        expanded = expand_chunks_to_paragraphs(
            payload.get("chunks") or [], conn, req.query_text, dedupe=True,
        )[: req.top_k]
    finally:
        conn.close()

    shaped = [s for c in expanded if (s := shape_chunk(c))]
    return {"query": req.query_text, "chunks": shaped}
