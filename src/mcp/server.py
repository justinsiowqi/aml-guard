"""
FastMCP server for AML Guard — packaged for H2OGPTe upload.

Installs dependencies at startup, then registers all AML investigation tools.
In dev mode, imports from src/mcp/tools_impl; in bundled mode (inside zip),
imports directly from mcp/tools_impl.
"""

import os
import sys
import subprocess
from typing import Optional


def _install_dependencies():
    server_dir = os.path.dirname(os.path.abspath(__file__))
    requirements_path = os.path.join(server_dir, "requirements.txt")
    if os.path.exists(requirements_path):
        print("[MCP Server] Installing dependencies...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "-q", "-r", requirements_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            print("[MCP Server] Dependencies installed.")
        except subprocess.CalledProcessError as e:
            print(f"[MCP Server] Warning: dependency install failed: {e}")
    else:
        print("[MCP Server] No requirements.txt found — skipping install.")


_install_dependencies()

from mcp.server.fastmcp import FastMCP

try:
    from src.mcp.tools_impl import (
        traverse_entity_network,
        detect_graph_anomalies,
        retrieve_typology_chunks,
    )
    from src.graph.connection import Neo4jConnection
except ImportError:
    from aml_tools.tools_impl import (
        traverse_entity_network,
        detect_graph_anomalies,
        retrieve_typology_chunks,
    )
    from aml_tools.connection import Neo4jConnection

mcp = FastMCP("aml-guard")


@mcp.tool()
def traverse_entity_network_tool(
    entity_id: str,
    entity_type: str,
    depth: int = 2,
) -> dict:
    """
    Pull the full entity subgraph: ownership chains, associated persons, and
    jurisdiction links for a given entity. Always call this first.
    """
    with Neo4jConnection() as conn:
        return traverse_entity_network(entity_id, entity_type, depth, conn=conn)


@mcp.tool()
def detect_graph_anomalies_tool(
    pattern_names: list,
    entity_id: Optional[str] = None,
) -> dict:
    """
    Run one or more named anomaly detection patterns against the graph.
    Available patterns: common_controller_across_shells, layered_ownership,
    high_risk_jurisdiction, shared_address_cluster, intermediary_shell_network,
    bearer_obscured_ownership.
    """
    with Neo4jConnection() as conn:
        return detect_graph_anomalies(pattern_names, entity_id, conn=conn)


@mcp.tool()
def retrieve_typology_chunks_tool(
    query_text: str,
    typology_id: Optional[str] = None,
    top_k: int = 5,
) -> dict:
    """
    Semantic search over MAS Notice 626 regulatory document chunks. Embed the
    query text and return the most relevant chunks by cosine similarity. Use to
    map observed entity behaviour to specific AML regulatory obligations.
    """
    with Neo4jConnection() as conn:
        return retrieve_typology_chunks(query_text, typology_id, top_k, conn=conn)



def main():
    mcp.run()


if __name__ == "__main__":
    main()
