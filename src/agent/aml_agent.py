"""
AML Guard — H2OGPTe agentic investigation loop.

Uses the H2OGPTe client and MCP tool registration from src/core to run a
single-agent financial crime investigation over the AML knowledge graph.
"""

from __future__ import annotations

import logging
import re

from src.core.client import create_client
from src.core.config import get_agent_config
from src.core.setup import create_collection, create_chat, register_mcp_tool, setup_agent_keys, upload_and_ingest_mcp
from src.core.prompt_loader import load_prompt, load_message
from src.mcp.schema import (
    AMLRiskResponse,
    GRAPH_SCHEMA_HINT,
    PATTERN_HINTS,
)

_VALID_VERDICTS = {"HIGH_RISK", "MEDIUM_RISK", "LOW_RISK", "CLEARED"}

# Field extractors — all lenient. Missing field → safe default (no exceptions).
_RE_VERDICT = re.compile(r"^\s*VERDICT\s*:\s*(\S+)", re.IGNORECASE | re.MULTILINE)
_RE_SCORE = re.compile(r"^\s*RISK_SCORE\s*:\s*([0-9]*\.?[0-9]+)", re.IGNORECASE | re.MULTILINE)
_RE_SUMMARY = re.compile(
    r"^\s*SUMMARY\s*:\s*(.+?)(?=^\s*[A-Z][A-Z_]{2,}\s*:|\Z)",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
_RE_TYPOLOGIES = re.compile(r"^\s*TRIGGERED_TYPOLOGIES\s*:\s*(.+?)$", re.IGNORECASE | re.MULTILINE)
_RE_CHUNKS = re.compile(r"^\s*CITED_CHUNKS\s*:\s*(.+?)$", re.IGNORECASE | re.MULTILINE)
_RE_ACTIONS = re.compile(
    r"^\s*RECOMMENDED_ACTIONS\s*:\s*\n?(.+?)(?=^\s*[A-Z][A-Z_]{2,}\s*:|\Z)",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
_RE_BULLET = re.compile(r"^\s*[-*•]\s*(.+?)\s*$", re.MULTILINE)


def _csv_list(raw: str | None) -> list[str]:
    if not raw or raw.strip().upper() == "NONE":
        return []
    return [p.strip() for p in raw.split(",") if p.strip() and p.strip().upper() != "NONE"]


def _parse_actions(block: str | None) -> list[str]:
    if not block:
        return []
    bullets = [m.group(1).strip() for m in _RE_BULLET.finditer(block)]
    return [b for b in bullets if b]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Agent config key — must match an entry under agents: in config/agents.yaml
# ---------------------------------------------------------------------------
_AGENT_NAME = "aml"

# ---------------------------------------------------------------------------
# Prompts — loaded from src/prompts/aml_sys.md and aml_message.md
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = load_prompt(_AGENT_NAME).format(
    GRAPH_SCHEMA_HINT=GRAPH_SCHEMA_HINT,
    PATTERN_HINTS=PATTERN_HINTS,
    AML_MAX_ITERATIONS=14,
)


class AMLAgent:
    """
    Single-agent AML investigator backed by H2OGPTe.

    Sets up a collection, registers the custom FastMCP server as a tool,
    creates a chat session, and runs the investigation via H2OGPTe's
    agentic chat API.

    Usage:
        agent = AMLAgent()
        response = agent.run("Investigate entity ENT-0042 for structuring risk.")
    """

    def __init__(self) -> None:
        self._client = create_client()
        self._config = get_agent_config(_AGENT_NAME)
        self._collection_id: str | None = None
        self._tool_ids: list | None = None

    def setup(self) -> None:
        """
        Create the H2OGPTe collection and register the MCP tool.

        Call once before run(). Idempotent — safe to call again if the
        collection or tool registration already exists.
        """
        self._collection_id = create_collection(
            self._client,
            collection_name="AML Guard",
            collection_desc="AML investigation knowledge graph collection.",
        )
        self._upload_id = upload_and_ingest_mcp(
            self._client,
            collection_id=self._collection_id,
        )
        self._tool_ids = register_mcp_tool(self._client)
        logger.info(
            "AMLAgent setup complete. collection=%s tools=%s",
            self._collection_id,
            self._tool_ids,
        )
        setup_agent_keys(self._client)

    def run(self, question: str) -> AMLRiskResponse:
        """
        Run a single AML investigation and return a structured risk response.

        Args:
            question: Natural-language investigation request, e.g.
                      "Investigate entity ENT-0042 for structuring risk."

        Returns:
            AMLRiskResponse with verdict, risk_score, findings, and evidence.
        """
        if self._collection_id is None:
            raise RuntimeError("Call setup() before run().")

        user_message = load_message(_AGENT_NAME).format(question=question)

        chat_session_id = create_chat(self._client, self._collection_id)
        logger.info("Chat session created: %s", chat_session_id)

        with self._client.connect(chat_session_id) as session:
            reply = session.query(
                message=user_message,
                system_prompt=_SYSTEM_PROMPT,
                llm=self._config.get("llm"),
                llm_args=dict(
                    temperature=self._config.get("temperature"),
                    use_agent=True,
                    agent_accuracy=self._config.get("agent_accuracy"),
                    agent_max_turns=self._config.get("agent_max_turns"),
                    agent_type=self._config.get("agent_type"),
                    agent_timeout=self._config.get("agent_timeout"),
                    agent_total_timeout=self._config.get("agent_total_timeout"),
                    agent_tools=self._config.get("agent_tools"),
                ),
                rag_config={"rag_type": "llm_only"},
            )

        logger.info("H2OGPTe reply received.")
        return self._parse_response(reply.content)

    def _parse_response(self, content: str) -> AMLRiskResponse:
        """Parse the H2OGPTe reply into an AMLRiskResponse.

        Lenient: any missing or malformed field falls back to a safe default
        (CLEARED / 0.0 / empty list). Raw `content` is preserved in `answer`.
        """
        raw_verdict = (_RE_VERDICT.search(content) or [None, ""])[1]
        verdict = raw_verdict.upper() if raw_verdict else ""
        if verdict not in _VALID_VERDICTS:
            verdict = "CLEARED"

        score_match = _RE_SCORE.search(content)
        try:
            score = float(score_match.group(1)) if score_match else 0.0
        except (TypeError, ValueError):
            score = 0.0
        score = max(0.0, min(1.0, score))

        typologies = _csv_list(
            (_RE_TYPOLOGIES.search(content) or [None, None])[1]
        )
        chunk_ids = _csv_list(
            (_RE_CHUNKS.search(content) or [None, None])[1]
        )
        actions_block = _RE_ACTIONS.search(content)
        actions = _parse_actions(actions_block.group(1) if actions_block else None)

        return AMLRiskResponse(
            session_id="",
            question="",
            answer=content,
            verdict=verdict,
            risk_score=score,
            triggered_typologies=typologies,
            cited_chunks=[{"chunk_id": cid} for cid in chunk_ids],
            recommended_actions=actions,
        )
