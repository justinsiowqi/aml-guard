"""
AML Guard — single agentic loop for financial crime investigation.

Replaces the three-agent architecture in loanguard-ai (Orchestrator +
ComplianceAgent + InvestigationAgent) with one agent that handles entity
traversal, typology matching, anomaly detection, and case persistence in a
single loop.

TODO: implement run() once Layer 1 data, Layer 2 typology docs, and the
      tool set (src/mcp/tools_impl.py) are in place.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Callable

from src.agent.config import (
    AML_MAX_HISTORY_PAIRS,
    AML_MAX_ITERATIONS,
    CACHE_CONTROL_EPHEMERAL,
    MODEL_MAIN,
    MAX_TOKENS,
    TEMPERATURE,
    make_anthropic_client,
)
from src.agent._security import guard_tool_result
from src.agent.utils import (
    call_claude_with_retry,
    extract_text,
    trim_message_history,
    truncate_tool_result,
)
from src.mcp.schema import (
    AMLRiskResponse,
    RiskVerdict,
    GRAPH_SCHEMA_HINT,
    PATTERN_HINTS,
)
from src.mcp.tool_defs import AML_TOOL_DEFS
from src.core.prompt_loader import load_prompt, load_message

if TYPE_CHECKING:
    from src.graph.connection import Neo4jConnection

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompts — loaded from src/prompts/*.md at import time
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = load_prompt("aml").format(
    GRAPH_SCHEMA_HINT=GRAPH_SCHEMA_HINT,
    PATTERN_HINTS=PATTERN_HINTS,
    AML_MAX_ITERATIONS=str(AML_MAX_ITERATIONS),
)

# User message template — rendered per-call inside run():
#   load_message("aml").format(question=question)

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class AMLAgent:
    """Single-agent AML investigator.

    Usage:
        agent = AMLAgent(execute_tool)
        response = agent.run("Investigate entity ENT-0042 for structuring risk.")
    """

    def __init__(self, execute_tool: Callable[[str, dict], dict]) -> None:
        self._execute_tool = execute_tool
        self._client = make_anthropic_client()

    def run(self, question: str) -> "AMLRiskResponse":
        """
        Run the agentic investigation loop for the given question.

        TODO: implement this method after completing:
          - src/mcp/tools_impl.py  (traverse_entity_network, detect_graph_anomalies,
                                    retrieve_typology_chunks, persist_case_finding,
                                    trace_evidence, read-neo4j-cypher)
          - src/mcp/tool_defs.py   (AML_TOOL_DEFS list)
          - src/mcp/schema.py      (GRAPH_SCHEMA_HINT, ANOMALY_REGISTRY, AMLRiskResponse)
          - src/graph/queries.py   (Cypher helpers for AML entity graph)

        Implementation guide (mirror compliance_agent.py from loanguard-ai):
          1. Pre-run traverse_entity_network for the entity, inject into messages
             with cache_control=ephemeral.
          2. Pre-run detect_graph_anomalies for entity-relevant patterns.
          3. Enter the agentic loop (max AML_MAX_ITERATIONS):
               a. Call Claude with system prompt + messages + AML_TOOL_DEFS.
               b. On stop_reason=end_turn: parse structured output → return AMLRiskResponse.
               c. On stop_reason=tool_use: execute each tool → guard_tool_result →
                  truncate → append to messages → trim history → next iteration.
          4. Parse verdict/risk_score/summary from Claude's final text block.
          5. Return AMLRiskResponse.
        """
        # TODO: remove this placeholder once implemented
        # Build the opening user message from the template:
        #   messages = [{"role": "user", "content": _USER_PROMPT_TEMPLATE.format(question=question)}]
        raise NotImplementedError(
            "AMLAgent.run() is not yet implemented. "
            "See the docstring above for the implementation guide."
        )

    def _parse_response(self, text: str, entity_id: str) -> "AMLRiskResponse":
        """
        Parse Claude's structured output into an AMLRiskResponse.

        TODO: implement to extract VERDICT, RISK_SCORE, SUMMARY,
              TRIGGERED_TYPOLOGIES, RECOMMENDED_ACTIONS from text.
        """
        raise NotImplementedError("_parse_response() not yet implemented.")
