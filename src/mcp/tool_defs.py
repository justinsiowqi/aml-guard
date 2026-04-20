"""
Tool definitions passed to Claude via the Anthropic tool-use API.

AML_TOOL_DEFS replaces the dual FASTMCP_TOOL_DEFS + NEO4J_MCP_TOOLS split
from loanguard-ai — one flat list for the single AML agent.

TODO: update input_schema for each tool once the Layer 1 schema is finalised.
      The descriptions are used verbatim by Claude to decide which tool to call —
      keep them precise and action-oriented.
"""

from __future__ import annotations

AML_TOOL_DEFS: list[dict] = [

    # ── Read-only Cypher (agent-generated queries) ──────────────────────────
    {
        "name": "read-neo4j-cypher",
        "description": (
            "Execute a read-only Cypher query against the AML graph database. "
            "Use for ad-hoc entity lookups, relationship traversal, and graph "
            "exploration not covered by the specialised tools below. "
            "WRITE operations (MERGE, CREATE, DELETE, SET) are blocked."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query":  {"type": "string", "description": "Parameterised Cypher query string."},
                "params": {"type": "object", "description": "Query parameter dict ($key → value)."},
            },
            "required": ["query"],
        },
    },

    # ── Specialised FastMCP tools ────────────────────────────────────────────
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

    {
        "name": "persist_case_finding",
        "description": (
            "Write the investigation results to the graph as a CaseAssessment with linked "
            "RiskFindings and InvestigationSteps (Layer 3). "
            "Always call this as the final step before producing your output."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_id":            {"type": "string"},
                "entity_type":          {"type": "string"},
                "verdict":              {"type": "string", "enum": ["HIGH_RISK", "MEDIUM_RISK", "LOW_RISK", "CLEARED"]},
                "risk_score":           {"type": "number", "description": "0.0–1.0"},
                "findings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "finding_type":  {"type": "string"},
                            "severity":      {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW", "INFO"]},
                            "description":   {"type": "string"},
                            "pattern_name":  {"type": "string"},
                        },
                        "required": ["finding_type", "severity", "description"],
                    },
                },
                "reasoning_steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description":   {"type": "string"},
                            "cypher_used":   {"type": "string"},
                            "section_ids":   {"type": "array", "items": {"type": "string"}},
                            "chunk_ids":     {"type": "array", "items": {"type": "string"}},
                            "chunk_scores":  {"type": "object"},
                        },
                        "required": ["description"],
                    },
                },
            },
            "required": ["entity_id", "entity_type", "verdict", "risk_score", "findings", "reasoning_steps"],
        },
    },

    {
        "name": "trace_evidence",
        "description": (
            "Retrieve all cited typology sections and chunks for a completed CaseAssessment. "
            "Use to populate the evidence panel in the UI."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "assessment_id": {"type": "string", "description": "The assessment_id returned by persist_case_finding."},
            },
            "required": ["assessment_id"],
        },
    },
]
