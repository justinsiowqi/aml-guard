"""
Parameterised Cypher helpers for the AML Guard graph.

Organised by layer:
  Layer 1 — entity graph lookups (entities + relationships)
  Layer 2 — typology document traversal (Regulation → Section → Chunk)
  Layer 3 — case assessment operations (write + read)

TODO: implement each function once your teammate has finalised the data model
      and loaded Layer 1. Use the schema in src/mcp/schema.py as the reference.

Cypher best practices (carry over from loanguard-ai):
  - Always use parameterised queries ($param) — never f-string interpolation.
  - For variable-length paths use size(r) not length(r).
  - Collect rel types with [rel IN r | type(rel)].
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.graph.connection import Neo4jConnection


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 1 — Entity graph
# ─────────────────────────────────────────────────────────────────────────────

def get_entity_subgraph(conn: "Neo4jConnection", entity_id: str) -> list[dict]:
    """
    Return the first-degree subgraph for any AML entity (Entity, Account, Transaction, etc.).

    TODO: implement once Layer 1 schema is finalised.
    Suggested query shape:
        MATCH (e {entity_id: $entity_id})
        OPTIONAL MATCH (e)-[r1]-(neighbour)
        OPTIONAL MATCH (neighbour)-[r2]-(second)
        RETURN ...
    """
    raise NotImplementedError("get_entity_subgraph() — implement after Layer 1 is loaded.")


def get_account_transactions(
    conn: "Neo4jConnection", account_id: str
) -> list[dict]:
    """
    Return all transactions linked to an account (inbound and outbound).

    TODO: implement once Layer 1 transaction nodes are confirmed.
    """
    raise NotImplementedError("get_account_transactions() — implement after Layer 1 is loaded.")


def get_entity_network(
    conn: "Neo4jConnection", entity_id: str, depth: int = 2
) -> list[dict]:
    """
    Return ownership/association chains up to `depth` hops from entity_id.

    TODO: implement. Variable-length path — use size(r) not length(r).
    """
    raise NotImplementedError("get_entity_network() — implement after Layer 1 is loaded.")


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 2 — Typology documents
# ─────────────────────────────────────────────────────────────────────────────

def get_typology_path(
    conn: "Neo4jConnection", entity_id: str, typology_id: str
) -> list[dict]:
    """
    Walk the Regulation → Section → Requirement → Indicator path for an entity.

    TODO: implement after Layer 2 extraction notebooks run.
    Mirror of loanguard-ai's get_compliance_path().
    """
    raise NotImplementedError("get_typology_path() — implement after Layer 2 is loaded.")


def vector_search_typology_chunks(
    conn: "Neo4jConnection",
    embedding: list[float],
    typology_id: str | None = None,
    top_k: int = 5,
    min_score: float = 0.75,
) -> list[dict]:
    """
    Vector similarity search over Layer 2 Chunk nodes using Neo4j vector index
    'chunk_embeddings' (cosine similarity, 1024-dim bge-large-en-v1.5).

    Optionally scoped to a single regulation via typology_id.
    """
    if typology_id:
        cypher = """
        CALL db.index.vector.queryNodes('chunk_embeddings', $top_k, $embedding)
        YIELD node AS c, score
        MATCH (req:Requirement)-[:HAS_CHUNK]->(c)
        MATCH (s:Section)-[:HAS_REQUIREMENT]->(req)
        WHERE req.regulation_id = $typology_id AND score >= $min_score
        RETURN c.chunk_id   AS chunk_id,
               c.text       AS text,
               c.paragraph  AS paragraph,
               s.section_id AS section_id,
               score
        ORDER BY score DESC
        LIMIT $top_k
        """
    else:
        cypher = """
        CALL db.index.vector.queryNodes('chunk_embeddings', $top_k, $embedding)
        YIELD node AS c, score
        MATCH (req:Requirement)-[:HAS_CHUNK]->(c)
        MATCH (s:Section)-[:HAS_REQUIREMENT]->(req)
        WHERE score >= $min_score
        RETURN c.chunk_id   AS chunk_id,
               c.text       AS text,
               c.paragraph  AS paragraph,
               s.section_id AS section_id,
               score
        ORDER BY score DESC
        LIMIT $top_k
        """
    return conn.run_query(cypher, {
        "embedding":   embedding,
        "top_k":       top_k,
        "min_score":   min_score,
        "typology_id": typology_id,
    })


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 3 — Case assessments (runtime, written by agent)
# ─────────────────────────────────────────────────────────────────────────────

def merge_case_assessment(
    conn: "Neo4jConnection",
    assessment_id: str,
    entity_id: str,
    entity_type: str,
    verdict: str,
    risk_score: float,
    agent: str = "AMLAgent",
    **kwargs: Any,
) -> list[dict]:
    """
    MERGE a CaseAssessment node and link it to the entity.

    TODO: implement. Mirror of loanguard-ai's merge_assessment().
    Node label: CaseAssessment
    Relationship: (Entity)-[:HAS_ASSESSMENT]->(CaseAssessment)
    """
    raise NotImplementedError("merge_case_assessment() — implement when Layer 3 schema is finalised.")


def batch_merge_risk_findings(
    conn: "Neo4jConnection", assessment_id: str, findings: list[dict]
) -> list[dict]:
    """
    Batch-MERGE RiskFinding nodes linked to assessment_id.

    TODO: implement. Mirror of loanguard-ai's batch_merge_findings().
    """
    raise NotImplementedError("batch_merge_risk_findings() — implement when Layer 3 schema is finalised.")


def batch_merge_investigation_steps(
    conn: "Neo4jConnection", assessment_id: str, steps: list[dict]
) -> list[dict]:
    """
    Batch-MERGE InvestigationStep nodes with CITES_TYPOLOGY / CITES_CHUNK edges.

    TODO: implement. Mirror of loanguard-ai's batch_merge_reasoning_steps().
    """
    raise NotImplementedError("batch_merge_investigation_steps() — implement when Layer 3 schema is finalised.")


def get_assessment_with_evidence(
    conn: "Neo4jConnection", assessment_id: str
) -> list[dict]:
    """
    Retrieve a CaseAssessment with all linked findings, steps, cited typologies, and chunks.

    TODO: implement. Mirror of loanguard-ai's get_assessment_with_evidence().
    """
    raise NotImplementedError("get_assessment_with_evidence() — implement when Layer 3 schema is finalised.")
