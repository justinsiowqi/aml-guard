"""
execute_tool dispatcher for the AML Guard agent.

Mirrors loanguard-ai/src/agent/dispatcher.py but wired to AML tools.
Neo4j MCP tools run Cypher via the shared conn.
FastMCP tools call tools_impl functions directly.

TODO: update _dispatch() as new tools are added to tools_impl.py.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any, Callable

from src.agent.config import WRITE_KEYWORDS

if TYPE_CHECKING:
    from src.graph.connection import Neo4jConnection

logger = logging.getLogger(__name__)

# Tools whose results are deterministic within a session — cache to avoid
# duplicate API calls when the agent retries the same tool.
_CACHEABLE_TOOLS: frozenset[str] = frozenset({
    "traverse_entity_network",
    "retrieve_typology_chunks",
})


def make_execute_tool(conn: "Neo4jConnection") -> Callable[[str, dict], Any]:
    """Return an execute_tool dispatcher bound to the given Neo4j connection."""
    _cache: dict[str, Any] = {}

    def execute_tool(tool_name: str, tool_input: dict) -> dict:
        if tool_name in _CACHEABLE_TOOLS:
            cache_key = tool_name + ":" + json.dumps(tool_input, sort_keys=True)
            if cache_key in _cache:
                logger.debug("Tool cache hit: %s", tool_name)
                return _cache[cache_key]

        logger.info("Tool: %s | inputs: %s", tool_name, list(tool_input.keys()))
        try:
            result = _dispatch(tool_name, tool_input, conn)
        except Exception as e:
            logger.error("Tool %s failed: %s", tool_name, e, exc_info=True)
            return {"error": str(e)}

        if tool_name in _CACHEABLE_TOOLS:
            _cache[cache_key] = result  # type: ignore[possibly-undefined]
        return result

    return execute_tool


def _dispatch(tool_name: str, tool_input: dict, conn: "Neo4jConnection") -> dict:
    # ── Neo4j MCP ──────────────────────────────────────────────────────────
    if tool_name == "read-neo4j-cypher":
        query  = tool_input.get("query", "")
        params = tool_input.get("params", {})
        query_words = set(re.findall(r"\b[A-Z]+\b", query.upper()))
        if query_words & WRITE_KEYWORDS:
            return {"error": "read-neo4j-cypher does not allow write operations."}
        return {"rows": conn.run_query(query, params)}

    elif tool_name == "write-neo4j-cypher":
        query  = tool_input.get("query", "")
        params = tool_input.get("params", {})
        return {"rows": conn.run_query(query, params)}

    # ── FastMCP — AML tools ────────────────────────────────────────────────
    # TODO: import and wire each tool from src.mcp.tools_impl as you implement them.
    # Pattern:
    #   elif tool_name == "traverse_entity_network":
    #       from src.mcp.tools_impl import traverse_entity_network
    #       return traverse_entity_network(**tool_input, conn=conn)

    elif tool_name == "traverse_entity_network":
        # TODO: implement in src/mcp/tools_impl.py
        return {"error": "traverse_entity_network not yet implemented."}

    elif tool_name == "detect_graph_anomalies":
        # TODO: implement in src/mcp/tools_impl.py
        return {"error": "detect_graph_anomalies not yet implemented."}

    elif tool_name == "retrieve_typology_chunks":
        # TODO: implement in src/mcp/tools_impl.py
        return {"error": "retrieve_typology_chunks not yet implemented."}

    elif tool_name == "persist_case_finding":
        # TODO: implement in src/mcp/tools_impl.py
        return {"error": "persist_case_finding not yet implemented."}

    elif tool_name == "trace_evidence":
        # TODO: implement in src/mcp/tools_impl.py
        return {"error": "trace_evidence not yet implemented."}

    else:
        return {"error": f"Unknown tool: {tool_name}"}
