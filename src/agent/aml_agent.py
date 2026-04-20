"""
AML Guard — H2OGPTe agentic investigation loop.

Uses the H2OGPTe client and MCP tool registration from src/core to run a
single-agent financial crime investigation over the AML knowledge graph.
"""

from __future__ import annotations

import logging

from src.core.client import create_client
from src.core.config import get_agent_config
from src.core.setup import create_collection, create_chat, register_mcp_tool
from src.core.prompt_loader import load_prompt, load_message
from src.mcp.schema import (
    AMLRiskResponse,
    GRAPH_SCHEMA_HINT,
    PATTERN_HINTS,
)

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
        self._tool_ids = register_mcp_tool(self._client)
        logger.info(
            "AMLAgent setup complete. collection=%s tools=%s",
            self._collection_id,
            self._tool_ids,
        )

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
                llm_args={
                    "temperature": self._config.get("temperature", 0.0),
                },
                timeout=120,
            )

        logger.info("H2OGPTe reply received.")
        return self._parse_response(reply.content)

    def _parse_response(self, content: str) -> AMLRiskResponse:
        """
        Parse the H2OGPTe reply into an AMLRiskResponse.

        TODO: extract VERDICT, RISK_SCORE, SUMMARY, TRIGGERED_TYPOLOGIES,
              and RECOMMENDED_ACTIONS from the structured output text using
              regex, then populate and return AMLRiskResponse.
        """
        raise NotImplementedError("_parse_response() not yet implemented.")
