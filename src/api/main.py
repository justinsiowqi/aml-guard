"""
FastAPI HTTP layer for the Next.js frontend.

Run from the project root:

    uvicorn src.api.main:app --reload --port 8000

The frontend (web/lib/api.ts) posts to ${NEXT_PUBLIC_API_BASE}/api/investigate
and expects a CaseAssessment-shaped response (see web/lib/types.ts).
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
from contextlib import asynccontextmanager
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
from src.api.jobs import (
    DEEP_PHASES,
    create_job,
    get_job,
    mark_cancelled,
    refresh_phase,
    update_job,
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



@asynccontextmanager
async def lifespan(app: FastAPI):
    # Collection creation + MCP upload are deferred to the first deep-analysis
    # click (_get_agent() is lazily initialised). No pre-warm thread here.
    yield


app = FastAPI(title="AML Guard API", version="0.1.0", lifespan=lifespan)

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
    """Start the H2OGPTe agent loop as a background job.

    The deterministic trunk runs synchronously (fast, and we need it to decide
    404-vs-202 before accepting the job). The 5–10 minute agent loop runs on
    a daemon thread; the response carries the job_id and the deterministic
    baseline so the UI can render immediately while polling for progress.
    """
    node_id, entity_type = resolve_entity(req.question)
    conn = _connect()
    try:
        case = build_case_assessment(req.question, node_id, entity_type, conn)
    finally:
        conn.close()
    if "_error" in case:
        raise HTTPException(status_code=404, detail=case["_error"])

    job = create_job(question=req.question)
    threading.Thread(
        target=_run_deep_job,
        args=(job.job_id, req.question, case),
        daemon=True,
        name=f"deep-{job.job_id[:8]}",
    ).start()
    return {"job_id": job.job_id, "case": case}


def _sanitize_agent_error(e: BaseException) -> str:
    """Turn an H2OGPTe SDK exception into a short, UI-friendly string.

    The SDK's SessionError on timeout dumps the entire serialised request
    (including system_prompt + full body) into its message string, which can
    be 10–50 KB of JSON noise. We detect known prefixes and replace the
    payload with a terse explanation; everything else gets length-capped.
    """
    err = str(e)
    err_class = type(e).__name__
    if "Request timed out" in err:
        return (
            "Agent run timed out — H2OGPTe didn't respond within the SDK's "
            "timeout window. The agent loop may still be running server-side; "
            "any steps completed before the timeout are shown below."
        )
    if "ConnectionResetError" in err or "Connection reset by peer" in err:
        return (
            "Connection to H2OGPTe reset — likely a transient network issue. "
            "Retry usually works."
        )
    # Generic fallback: cap the length so a future SDK error type doesn't
    # flood the UI.
    if len(err) > 240:
        err = err[:240].rstrip() + "…"
    return f"{err_class}: {err}"


def _run_deep_job(job_id: str, question: str, case: dict) -> None:
    """Background worker that runs the H2OGPTe agent and stores the result.

    Calls _get_agent() inside the thread so the API response isn't blocked by
    a cold-start setup (collection create + MCP upload). Registers the
    chat_session_id via update_job as soon as the agent provides it, so the
    status endpoint can begin polling H2OGPTe immediately.
    """
    def _on_started(chat_session_id: str) -> None:
        update_job(job_id, chat_session_id=chat_session_id)

    def _on_reply(reply: object) -> None:
        update_job(
            job_id,
            input_tokens=getattr(reply, "input_tokens", None),
            output_tokens=getattr(reply, "output_tokens", None),
        )

    try:
        agent = _get_agent()
        # E' — Pre-loaded Context Agent. Pass the deterministic trunk's case
        # assessment to the agent so it doesn't re-run the three baseline MCP
        # tools. The agent reads the evidence directly from its user message
        # and can still call MCP tools for genuine follow-ups (e.g. expanding
        # anomaly detection to an unscoped Intermediary).
        logger.info(
            "Deep job %s — invoking agent with pre-loaded trunk evidence "
            "(nodes=%d edges=%d findings=%d chunks=%d)",
            job_id,
            len((case.get("subgraph") or {}).get("nodes") or []),
            len((case.get("subgraph") or {}).get("edges") or []),
            len(case.get("findings") or []),
            len(case.get("typology_chunks") or []),
        )
        agent_resp = agent.start_async(
            question,
            on_started=_on_started,
            on_reply=_on_reply,
            trunk_evidence=case,
        )
    except Exception as e:
        logger.exception("Deep-analysis agent failed (job=%s)", job_id)
        update_job(job_id, status="error", error=_sanitize_agent_error(e))
        return

    # If the client gave up while we were running, drop the result on the
    # floor — the H2OGPTe call already billed, but the user no longer cares.
    cur = get_job(job_id)
    if cur and cur.status == "cancelled":
        logger.info("Job %s already cancelled; discarding agent result", job_id)
        return

    # Confirm the agent's MCP tool usage from the final chat-session events.
    # Under E' the agent should NEED to call zero tools for clean runs, and 1–2
    # tools for follow-up cases. Logging this proves the agentic + Neo4j
    # integration is still live (i.e. the agent CAN call MCP tools — we just
    # don't make it run the baseline three).
    _log_followup_tool_calls(job_id, question)

    try:
        merged = merge_agent_into_case(case, agent_resp)
    except Exception as e:
        logger.exception("merge_agent_into_case failed (job=%s)", job_id)
        update_job(job_id, status="error", error=f"Merge failed: {e}")
        return

    update_job(
        job_id,
        status="done",
        result=merged,
        phase_idx=len(DEEP_PHASES) - 1,
        phase_label="Done",
    )


# Names of the three MCP tools the agent can call as follow-ups under E'.
# Used by _log_followup_tool_calls to scan code blocks for evidence of use.
_AML_MCP_TOOL_NAMES = (
    "traverse_entity_network",
    "detect_graph_anomalies",
    "retrieve_typology_chunks",
)


def _log_followup_tool_calls(job_id: str, question: str) -> None:
    """Inspect the job's accumulated `agent_events` and log a one-line summary
    of which MCP tools the agent called (and how many times). Under E' this is
    expected to be 0 for clean runs and 1-2 for follow-up cases.

    Reads from the job registry rather than re-fetching from H2OGPTe — the
    polling loop has already populated `agent_events` with the structured
    turn cards (each carrying the agent's executed code block, if any).
    """
    try:
        job = get_job(job_id)
        if job is None:
            return
        # Build a single haystack from every emitted turn's code + message so
        # we catch tool calls regardless of whether they appear in the actual
        # code block or just in the agent's narration of what it did.
        haystack_parts: list[str] = []
        for ev in job.agent_events or []:
            if ev.get("kind") != "turn":
                continue
            haystack_parts.append((ev.get("code") or "") + " " + (ev.get("message") or ""))
        haystack = " ".join(haystack_parts).lower()

        counts = {name: haystack.count(name) for name in _AML_MCP_TOOL_NAMES}
        total = sum(counts.values())
        logger.info(
            "Deep job %s — agent emitted %d turn cards; follow-up MCP tool references: total=%d details=%s | question=%r",
            job_id,
            sum(1 for ev in (job.agent_events or []) if ev.get("kind") == "turn"),
            total,
            counts,
            (question or "")[:80],
        )
    except Exception as e:
        # Logging must never affect the user response.
        logger.debug("Failed to log follow-up tool calls for job %s: %s", job_id, e)


@app.get("/api/investigate/deep/status/{job_id}")
def deep_status(job_id: str) -> dict:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="unknown job")
    if job.status == "running" and job.chat_session_id:
        try:
            refresh_phase(job, _get_agent().client)
            job = get_job(job_id) or job
        except Exception as e:
            logger.debug("refresh_phase failed for job %s: %s", job_id, e)
    return {
        "status": job.status,
        "phase_idx": job.phase_idx,
        "phase_label": job.phase_label,
        "elapsed_seconds": int(time.monotonic() - job.started_at),
        "input_tokens": job.input_tokens,
        "output_tokens": job.output_tokens,
        "agent_events": list(job.agent_events),
        "result": job.result,
        "error": job.error,
    }


@app.post("/api/investigate/deep/cancel/{job_id}")
def deep_cancel(job_id: str) -> dict:
    if not mark_cancelled(job_id):
        raise HTTPException(status_code=404, detail="unknown job")
    return {
        "status": "cancelled",
        "note": "agent run continues server-side and still bills; the UI just stops watching.",
    }


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
