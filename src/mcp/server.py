"""
FastMCP server registration for AML Guard tools.

TODO: uncomment each @mcp.tool() registration as the corresponding
      function in tools_impl.py is implemented and tested.
"""

from fastmcp import FastMCP

mcp = FastMCP("aml-guard")

# TODO: import and register each tool from tools_impl as you implement them.
# Pattern:
#
# from src.mcp.tools_impl import traverse_entity_network
# @mcp.tool()
# def traverse_entity_network_tool(entity_id: str, entity_type: str, depth: int = 2) -> dict:
#     from src.graph.connection import Neo4jConnection
#     with Neo4jConnection() as conn:
#         return traverse_entity_network(entity_id, entity_type, depth, conn=conn)
