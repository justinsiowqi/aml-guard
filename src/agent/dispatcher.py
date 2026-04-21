"""
execute_tool dispatcher for the AML Guard agent.

Routes tool calls to custom FastMCP tool implementations in src/mcp/tools_impl.py.
The shared Neo4jConnection is passed through so tools don't open their own connections.

TODO: update _dispatch() as new tools are added to tools_impl.py.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from src.graph.connection import Neo4jConnection

logger = logging.getLogger(__name__)

# Tools whose results are deterministic within a session — cache to avoid
# duplicate calls when the agent retries the same tool.
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
    # ── FastMCP — AML tools ────────────────────────────────────────────────
    # TODO: import and wire each tool from src.mcp.tools_impl as you implement them.
    # Pattern:
    #   elif tool_name == "traverse_entity_network":
    #       from src.mcp.tools_impl import traverse_entity_network
    #       return traverse_entity_network(**tool_input, conn=conn)

    if tool_name == "traverse_entity_network":
        from src.mcp.tools_impl import traverse_entity_network
        return traverse_entity_network(**tool_input, conn=conn)

    elif tool_name == "detect_graph_anomalies":
        from src.mcp.tools_impl import detect_graph_anomalies
        return detect_graph_anomalies(**tool_input, conn=conn)

    elif tool_name == "retrieve_typology_chunks":
        from src.mcp.tools_impl import retrieve_typology_chunks
        return retrieve_typology_chunks(**tool_input, conn=conn)

    else:
        return {"error": f"Unknown tool: {tool_name}"}
