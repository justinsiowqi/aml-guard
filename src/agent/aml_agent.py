"""
AML Guard — H2OGPTe agentic investigation loop.

Uses the H2OGPTe client and MCP tool registration from src/core to run a
single-agent financial crime investigation over the AML knowledge graph.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable

from h2ogpte_observability import traced_query

from src.core.client import create_client
from src.core.config import get_agent_config
from src.core.setup import (
    SERVER_FILENAME,
    create_collection,
    create_chat,
    register_mcp_tool,
    setup_agent_keys,
    upload_and_ingest_mcp,
)
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

# Patterns that disqualify a parsed bullet from being a recommended action.
# Used by _parse_actions to strip noise from the agent's actions block.
_ACTION_NOISE = re.compile(
    r"^[-–—]+$"                              # bare separator lines: --, ---, —
    r"|^[*_]?would you\b"                    # follow-up question openers
    r"|^[*_]?do you want"
    r"|^[*_]?shall i\b"
    r"|^[*_]?should i\b"
    r"|^[*_]?is there\b"
    r"|^\*{1,2}[^*]+\*{1,2}\s*$"            # line that is only bold/italic text (markdown artefact)
    r"|\?[*_]*$",                            # anything ending in a question mark
    re.I,
)


def _evidence_placeholders(case: dict[str, Any] | None) -> dict[str, str]:
    """Render the trunk's case-assessment dict into the four JSON placeholders
    expected by aml_message.md: subject, subgraph, findings, typology_chunks.

    Each is a pretty-printed JSON block (indent=2) so the agent can scan it as
    plain text. Missing keys render as `{}` / `[]` so the prompt still has a
    syntactically valid placeholder even in degraded cases.
    """
    case = case or {}
    return {
        "subject": json.dumps(case.get("subject") or {}, indent=2, ensure_ascii=False),
        "subgraph": json.dumps(case.get("subgraph") or {"nodes": [], "edges": []}, indent=2, ensure_ascii=False),
        "findings": json.dumps(case.get("findings") or [], indent=2, ensure_ascii=False),
        "typology_chunks": json.dumps(case.get("typology_chunks") or [], indent=2, ensure_ascii=False),
    }


def _csv_list(raw: str | None) -> list[str]:
    if not raw or raw.strip().upper() == "NONE":
        return []
    return [p.strip() for p in raw.split(",") if p.strip() and p.strip().upper() != "NONE"]


def _parse_actions(block: str | None) -> list[str]:
    if not block:
        return []
    actions: list[str] = []
    for m in _RE_BULLET.finditer(block):
        text = m.group(1).strip()
        # Strip markdown bold/italic wrappers from the whole action text.
        text = re.sub(r"^\*{1,2}(.+?)\*{1,2}$", r"\1", text).strip()
        if not text:
            continue
        if _ACTION_NOISE.search(text):
            continue
        actions.append(text)
    return actions

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

        # Use print() for these diagnostics so they're visible without
        # having to configure the root logger to INFO level.
        try:
            tools = self._client.get_custom_agent_tools()
            print(f"[diag] get_custom_agent_tools() -> {len(tools or [])} tools")
            for t in (tools or []):
                print(
                    f"  tool name={getattr(t, 'tool_name', None)} "
                    f"type={getattr(t, 'tool_type', None)} "
                    f"id={getattr(t, 'id', None)}"
                )
        except Exception as e:
            print(f"[diag] get_custom_agent_tools() failed: {e}")
        try:
            prefs = self._client.get_agent_tool_preference() or []
            in_prefs = SERVER_FILENAME in prefs
            print(
                f"[diag] get_agent_tool_preference(): {SERVER_FILENAME} "
                f"{'ENABLED' if in_prefs else 'MISSING'} (list size={len(prefs)})"
            )
            if not in_prefs:
                print(f"[diag] WARNING: agent will NOT see {SERVER_FILENAME} functions.")
        except Exception as e:
            print(f"[diag] get_agent_tool_preference() failed: {e}")

    def run(self, question: str, trunk_evidence: dict[str, Any] | None = None) -> AMLRiskResponse:
        """Synchronous wrapper around start_async — kept for callers that don't
        need to observe the chat_session_id while the agent loop is running."""
        return self.start_async(
            question,
            on_started=lambda _csid: None,
            on_reply=lambda _reply: None,
            trunk_evidence=trunk_evidence,
        )

    @property
    def client(self):
        """Exposed for the async deep-analysis path so the job-status endpoint
        can poll list_chat_messages without re-creating a client."""
        return self._client

    def start_async(
        self,
        question: str,
        on_started: Callable[[str], None],
        on_reply: Callable[[object], None],
        trunk_evidence: dict[str, Any] | None = None,
    ) -> AMLRiskResponse:
        """
        Run a single AML investigation, calling `on_started(chat_session_id)`
        as soon as the chat session is created (before the long-blocking
        session.query). This lets a caller wire the chat_session_id into a
        job registry so a separate request can poll progress.

        Args:
            question: Natural-language investigation request.
            on_started: Called with the chat_session_id once it's available.
                        Exceptions from this callback are logged and swallowed.
            on_reply: Called with the raw H2OGPTe reply object once the agent
                      loop completes (before parsing). Used to capture
                      tokens / cost into the job registry.
            trunk_evidence: Deterministic AML trunk results (subject, subgraph,
                            findings, typology_chunks). Injected into the user
                            message so the agent can synthesise the verdict
                            without re-calling the three baseline MCP tools.
                            See src/prompts/aml_message.md for the placeholders.
                            If None, the agent runs in legacy mode (placeholders
                            substituted with empty {}).

        Returns:
            AMLRiskResponse with verdict, risk_score, findings, and evidence.
        """
        if self._collection_id is None:
            raise RuntimeError("Call setup() before run().")

        user_message = load_message(_AGENT_NAME).format(
            question=question,
            **_evidence_placeholders(trunk_evidence),
        )

        chat_session_id = create_chat(self._client, self._collection_id)
        logger.info("Chat session created: %s", chat_session_id)
        try:
            on_started(chat_session_id)
        except Exception as e:
            logger.warning("on_started callback raised: %s", e)

        # SDK-level HTTP timeout. Must be >= agent_total_timeout (server-side
        # cap on the whole agent loop) plus a small margin, otherwise the
        # client tears down the connection while the agent is still running
        # and we get the spurious "Request timed out" error from session.py.
        sdk_timeout = max(600, int(self._config.get("agent_total_timeout") or 0) + 60)

        with self._client.connect(chat_session_id) as session:
            reply = traced_query(
                session,
                user_message,
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
                timeout=sdk_timeout,
            )

        print(
            f"[diag] H2OGPTe reply received. content_len={len(reply.content or '')} "
            f"input_tokens={getattr(reply, 'input_tokens', '?')} "
            f"output_tokens={getattr(reply, 'output_tokens', '?')} "
            f"error={getattr(reply, 'error', None)}"
        )
        try:
            on_reply(reply)
        except Exception as e:
            logger.warning("on_reply callback raised: %s", e)
        # Dump the chat-session messages so we can see whether tool calls
        # actually fired. Each tool invocation usually shows up as a
        # ChatMessage with type_list containing "tool" entries.
        try:
            messages = self._client.list_chat_messages(
                chat_session_id, offset=0, limit=50
            )
            if messages:
                print(f"[diag] Chat session {chat_session_id} produced {len(messages)} messages.")
                for m in messages:
                    preview = (getattr(m, "content", "") or "")[:200].replace("\n", " ")
                    print(
                        f"  msg id={getattr(m, 'id', '?')} "
                        f"type_list={getattr(m, 'type_list', None)} "
                        f"len(content)={len(getattr(m, 'content', '') or '')} "
                        f"preview={preview!r}"
                    )
        except Exception as e:
            print(f"[diag] list_chat_messages diagnostics failed: {e}")

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
