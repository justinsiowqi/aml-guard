"""
FastAPI HTTP layer for the Next.js frontend.

Run from the project root:

    uvicorn src.api.main:app --reload --port 8000

The frontend (web/lib/api.ts) posts to ${NEXT_PUBLIC_API_BASE}/api/investigate
and expects a CaseAssessment-shaped response (see web/lib/types.ts).
"""

from __future__ import annotations

import logging

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.api.assembler import (
    build_case_assessment,
    expand_chunks_to_paragraphs,
    shape_chunk,
)
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


# TODO(agent-loop): replace with AMLAgent-driven entity resolution once
# src/agent/aml_agent.py::_parse_response is implemented.
NIELSEN_NODE_ID = "10122953"
NIELSEN_TYPE = "Company"


def resolve_entity(question: str) -> tuple[str, str]:
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
    return result


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
            payload.get("chunks") or [], conn, dedupe=True,
        )[: req.top_k]
    finally:
        conn.close()

    shaped = [s for c in expanded if (s := shape_chunk(c))]
    return {"query": req.query_text, "chunks": shaped}
