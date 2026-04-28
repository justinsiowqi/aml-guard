"""
Parameterised Cypher helpers for the AML Guard graph.

Organised by layer:
  Layer 1 — entity graph lookups (entities + relationships)
  Layer 2 — typology document traversal (Regulation → Section → Chunk)

Cypher best practices:
  - Always use parameterised queries ($param) — never f-string interpolation.
  - For variable-length paths use size(r) not length(r).
  - Collect rel types with [rel IN r | type(rel)].
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.graph.connection import Neo4jConnection


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 1 — Entity graph
# ─────────────────────────────────────────────────────────────────────────────

def get_entity_subgraph(conn: "Neo4jConnection", entity_id: str) -> list[dict]:
    """
    Return the first-degree subgraph for a Layer 1 entity matched by name or node_id.

    Searches across Person, Company, Intermediary, Address, and Jurisdiction.
    Returns the matching node plus all directly connected neighbours with
    relationship type and direction.
    """
    return conn.run_query("""
        MATCH (e)
        WHERE (e.node_id = $entity_id OR e.name = $entity_id OR e.jurisdiction_id = $entity_id)
          AND any(lbl IN labels(e) WHERE lbl IN ['Person','Company','Intermediary','Address','Jurisdiction'])
        OPTIONAL MATCH (e)-[r]-(neighbour)
        RETURN
            e.node_id                          AS entity_id,
            labels(e)[0]                       AS entity_type,
            e.name                             AS entity_name,
            e.jurisdiction                     AS jurisdiction,
            e.status                           AS status,
            e.source_leak                      AS source_leak,
            collect(DISTINCT {
                neighbour_id:   coalesce(neighbour.node_id, neighbour.jurisdiction_id),
                neighbour_type: labels(neighbour)[0],
                neighbour_name: neighbour.name,
                rel_type:       type(r),
                rel_props:      properties(r)
            })                                 AS neighbours
        LIMIT 1
    """, {"entity_id": entity_id})


def get_intermediary_network(
    conn: "Neo4jConnection", intermediary_id: str
) -> list[dict]:
    """
    Return all companies set up by an intermediary (registered agent / law firm),
    with their jurisdiction and AML risk rating.

    Core AML signal: a single intermediary setting up many shells in high-risk
    jurisdictions (e.g. Mossack Fonseca / Panama Papers pattern).
    """
    return conn.run_query("""
        MATCH (i:Intermediary)-[:INTERMEDIARY_OF]->(c:Company)
        WHERE i.node_id = $intermediary_id OR i.name = $intermediary_id
        OPTIONAL MATCH (c)-[:INCORPORATED_IN]->(j:Jurisdiction)
        OPTIONAL MATCH (c)-[:REGISTERED_AT]->(a:Address)
        RETURN
            i.node_id           AS intermediary_id,
            i.name              AS intermediary_name,
            i.countries         AS intermediary_country,
            c.node_id           AS company_id,
            c.name              AS company_name,
            c.status            AS company_status,
            c.incorporation_date AS incorporation_date,
            c.service_provider  AS service_provider,
            j.jurisdiction_id   AS jurisdiction_id,
            j.name              AS jurisdiction_name,
            j.aml_risk_rating   AS aml_risk_rating,
            a.address           AS registered_address
        ORDER BY j.aml_risk_rating, c.name
    """, {"intermediary_id": intermediary_id})


def get_entity_network(
    conn: "Neo4jConnection", entity_id: str, depth: int = 2
) -> list[dict]:
    """
    Return ownership/association chains up to `depth` hops from a Company or Person,
    traversing IS_OFFICER_OF, INTERMEDIARY_OF, SHARES_ADDRESS_WITH, and INCORPORATED_IN.
    """
    return conn.run_query("""
        MATCH (start)
        WHERE (start.node_id = $entity_id OR start.name = $entity_id)
          AND any(lbl IN labels(start) WHERE lbl IN ['Person','Company','Intermediary'])
        MATCH path = (start)-[r:IS_OFFICER_OF|INTERMEDIARY_OF|SHARES_ADDRESS_WITH|INCORPORATED_IN*1..2]-(connected)
        RETURN
            start.node_id                          AS origin_id,
            labels(start)[0]                       AS origin_type,
            coalesce(connected.node_id, connected.jurisdiction_id) AS connected_id,
            coalesce(connected.name, connected.jurisdiction_id)    AS connected_name,
            labels(connected)[0]                   AS connected_type,
            [rel IN r | type(rel)]                 AS hop_types,
            size(r)                                AS depth
        ORDER BY depth, connected_type
        LIMIT 50
    """, {"entity_id": entity_id, "depth": depth})


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 2 — Typology documents
# ─────────────────────────────────────────────────────────────────────────────

def get_typology_path(
    conn: "Neo4jConnection", typology_id: str
) -> list[dict]:
    """
    Return the full Regulation → Section → Requirement hierarchy for a regulation,
    optionally filtered to sections relevant to the entity's jurisdiction or risk profile.
    """
    # AML-relevant sections: 4 (risk assessment), 6 (CDD), 7 (EDD), 8 (beneficial ownership), 11 (record keeping)
    return conn.run_query("""
        MATCH (reg:Regulation {regulation_id: $typology_id})
        MATCH (reg)-[:HAS_SECTION]->(s:Section)
        WHERE s.section_number IN $aml_sections
        MATCH (s)-[:HAS_REQUIREMENT]->(req:Requirement)
        OPTIONAL MATCH (req)-[:DEFINES_THRESHOLD]->(t:Threshold)
        RETURN
            reg.regulation_id   AS regulation_id,
            reg.name            AS regulation_name,
            s.section_id        AS section_id,
            s.section_number    AS section_number,
            s.title             AS section_title,
            req.requirement_id  AS requirement_id,
            req.paragraph       AS paragraph,
            req.text            AS requirement_text,
            collect(DISTINCT {
                threshold_id:   t.threshold_id,
                metric:         t.metric,
                operator:       t.operator,
                value:          t.value,
                unit:           t.unit,
                threshold_type: t.threshold_type
            })                  AS thresholds
        ORDER BY s.section_number, req.paragraph
    """, {
        "typology_id":  typology_id,
        "aml_sections": ["4", "6", "7", "8", "11"],
    })


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


def get_full_paragraph_text(
    conn: "Neo4jConnection", section_id: str, paragraph: str
) -> str:
    """
    Concatenate every Chunk belonging to a (section_id, paragraph) pair,
    in chunk_index order, so the user sees the whole paragraph rather
    than a single embedding-sized fragment.
    """
    rows = conn.run_query(
        """
        MATCH (s:Section {section_id: $section_id})-[:HAS_REQUIREMENT]->(req:Requirement)-[:HAS_CHUNK]->(c:Chunk)
        WHERE c.paragraph = $paragraph
        RETURN c.text AS text
        ORDER BY c.chunk_index
        """,
        {"section_id": section_id, "paragraph": paragraph},
    )
    return " ".join((r.get("text") or "").strip() for r in rows if r.get("text"))


