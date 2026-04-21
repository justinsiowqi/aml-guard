"""
Tool definitions for the AML Guard agent — custom FastMCP tools only.

All tools are implemented in src/mcp/tools_impl.py and served by src/mcp/server.py.

TODO: update input_schema for each tool once the Layer 1 schema is finalised.
      The descriptions are used verbatim by the model to decide which tool to call —
      keep them precise and action-oriented.
"""

from __future__ import annotations

AML_TOOL_DEFS: list[dict] = [

    # ── Custom FastMCP tools ─────────────────────────────────────────────────
    {
        "name": "traverse_entity_network",
        "description": (
            "Pull the full entity subgraph: accounts, transactions, ownership chains, "
            "associated persons, and jurisdiction links for a given entity. "
            "Always call this first before any other tool."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                # TODO: update property names to match your entity ID convention.
                "entity_id":   {"type": "string", "description": "Primary entity identifier (e.g. ENT-0042)."},
                "entity_type": {"type": "string", "description": "Node label (e.g. Entity, Account, Alert)."},
                "depth":       {"type": "integer", "description": "Traversal depth (default 2).", "default": 2},
            },
            "required": ["entity_id", "entity_type"],
        },
    },

    {
        "name": "detect_graph_anomalies",
        "description": (
            "Run one or more named anomaly detection patterns against the graph. "
            "Returns structured results per pattern. Always run after traverse_entity_network."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "List of patterns to run. Available: "
                        "transaction_structuring, rapid_fund_movement, layered_ownership, "
                        "high_risk_jurisdiction, pep_association, smurfing."
                    ),
                },
                "entity_id": {
                    "type": "string",
                    "description": "If provided, scope results to this entity only.",
                },
            },
            "required": ["pattern_names"],
        },
    },

    {
        "name": "retrieve_typology_chunks",
        "description": (
            "Semantic search over FATF/AUSTRAC typology document chunks. "
            "Embed the query text and return the most relevant chunks by cosine similarity. "
            "Use to link observed behaviour to known financial crime typologies."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query_text":  {"type": "string", "description": "Natural-language description of the observed behaviour."},
                "typology_id": {"type": "string", "description": "Restrict search to a specific typology document (optional)."},
                "top_k":       {"type": "integer", "description": "Number of chunks to return (default 5).", "default": 5},
            },
            "required": ["query_text"],
        },
    },

]
