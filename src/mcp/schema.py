"""
Shared schema, dataclasses, and anomaly registry for AML Guard.

Provides:
  GRAPH_SCHEMA_HINT  — injected into H2OGPTe system prompt
  ANOMALY_REGISTRY   — AML detection patterns with Cypher
  Dataclasses        — AMLRiskResponse, RiskFinding
  Enums              — RiskVerdict, Severity
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# Graph Schema Hint
# Keep this accurate — H2OGPTe uses it to generate valid Cypher without
# calling get-neo4j-schema on every turn.
# ─────────────────────────────────────────────────────────────────────────────

GRAPH_SCHEMA_HINT = """
## Neo4j Graph Schema — AML Guard

Investigation domain: offshore shell-company networks (ICIJ Panama Papers subset)
cross-referenced against Singapore's AML regulation (MAS Notice 626).

Account and Transaction nodes are deliberately out of scope in this build —
the demo focuses on corporate-ownership opacity, not bank-to-bank money flows.

### LAYER 1 — Offshore Entity Graph

Node: Person
  Properties: node_id (str, unique),   # ICIJ officer node_id (numeric string)
              name (str),
              countries (str),         # human-readable country names
              country_codes (str),     # comma-separated ISO alpha-3
              source_leak (str),       # e.g. "Panama Papers"
              valid_until (str),
              note (str)

Node: Company
  Properties: node_id (str, unique),   # ICIJ entity node_id
              name (str),
              original_name (str),
              former_name (str),
              jurisdiction (str),      # ISO alpha-3 of incorporation
              jurisdiction_description (str),
              company_type (str),
              address (str),           # inline address string from ICIJ
              incorporation_date (str),
              inactivation_date (str),
              struck_off_date (str),
              status (str),
              service_provider (str),  # e.g. "Mossack Fonseca"
              ibcRUC (str),
              country_codes (str),
              countries (str),
              source_leak (str)

Node: Intermediary
  Properties: node_id (str, unique),
              name (str),
              status (str),
              internal_id (str),
              address (str),
              countries (str),
              country_codes (str),
              source_leak (str)

Node: Address   # derived from inline Company/Intermediary address strings
  Properties: node_id (str, unique),   # synthetic prefix "addr_<int>"
              address (str),           # normalised address text
              source (str)             # always "derived_inline"

Node: Jurisdiction
  Properties: jurisdiction_id (str, unique),  # ISO alpha-3 code (e.g. "BVI", "PMA")
              name (str),
              country (str),
              country_code (str),
              aml_risk_rating (str)    # "high" | "medium" | "low"

### LAYER 1 Relationships

(Person)-[:IS_OFFICER_OF {role, source_leak, status, start_date, end_date, link}]->(Company)
  # ICIJ rel_type "officer_of". `role` carries the raw role string
  # (e.g. "director", "shareholder", "beneficial owner").

(Intermediary)-[:INTERMEDIARY_OF {source_leak, status, start_date, end_date, link}]->(Company)
  # ICIJ rel_type "intermediary_of" — the registered agent that set up the company.

(Company)-[:REGISTERED_AT {source_leak, link}]->(Address)
  # Derived from the inline `address` column. Enables shared-address detection.

(Intermediary)-[:REGISTERED_AT {source_leak, link}]->(Address)
  # Same derivation for intermediaries.

(Company)-[:SHARES_ADDRESS_WITH {address_node_id, source_leak}]->(Company)
  # Derived red flag: two Companies sharing one Address (clusters of 2-8 only;
  # larger clusters are registered-agent buildings and are filtered out).

(Company)-[:SIMILAR_TO {source_leak, link}]->(Company)
  # ICIJ rel_type "similar" — companies ICIJ flagged as closely matching.

(Company)-[:INCORPORATED_IN]->(Jurisdiction)
  # Derived at ingest from Company.jurisdiction → Jurisdiction.jurisdiction_id.

### LAYER 2 — MAS Notice 626 Regulatory Knowledge

Node: Regulation
  Properties: regulation_id (str, unique),  # e.g. "MAS-626"
              name (str),
              issuing_body (str),            # "Monetary Authority of Singapore"
              document_type (str),           # "notice"
              effective_date (date),
              last_revised (date),
              is_enforceable (bool),
              source_file (str)

Node: Section
  Properties: section_id (str, unique),      # "MAS-626-S6"
              regulation_id (str),
              section_number (str),
              title (str),
              paragraph_count (int),
              word_count (int)

Node: Requirement   # paragraph-level; equivalent to LoanGuard's "requirement"
  Properties: requirement_id (str, unique),  # "MAS-626-6.3"
              section_id (str),
              paragraph (str),               # "6.3"
              text (str),                    # full paragraph text
              word_count (int)

Node: Threshold   # numeric thresholds extracted from requirement text
  Properties: threshold_id (str, unique),
              paragraph (str),
              metric (str),                  # "transaction_value" | "percentage" | "duration"
              operator (str),                # ">=" | "<=" | "=="
              value (str),                   # numeric as string
              unit (str),                    # "SGD" | "percent" | "day" | "month" | "year"
              context (str),                 # ±80 char window of source text
              threshold_type (str)           # "trigger" | "informational"

Node: Chunk
  Properties: chunk_id (str, unique),        # "6.3-c0"
              paragraph (str),
              text (str),
              chunk_index (int),
              embedding (list[float])        # dense vector from H2OGPTe
                                             # client.encode_for_retrieval(); populated by
                                             # notebook 215. Dimension depends on the model
                                             # (e.g. 1024 for mxbai-embed-large-v1).

### LAYER 2 Relationships

(Regulation)-[:HAS_SECTION]->(Section)
(Section)-[:NEXT_SECTION]->(Section)           # section-number ordering
(Section)-[:HAS_REQUIREMENT]->(Requirement)
(Requirement)-[:DEFINES_THRESHOLD]->(Threshold)
(Requirement)-[:HAS_CHUNK]->(Chunk)
(Chunk)-[:NEXT_CHUNK]->(Chunk)                 # chunk-index ordering within paragraph
(Requirement)-[:CROSS_REFERENCES]->(Requirement)
(Chunk)-[:SEMANTICALLY_SIMILAR {score}]->(Chunk)  # optional, not built by default;
                                                  # notebook 215 only creates the vector
                                                  # index `chunk_embeddings`. Add this edge
                                                  # in a follow-up pass if needed.


### Cypher Best Practices
- Always use parameterised queries ($param) — never string interpolation.
- For variable-length paths use size(r) not length(r).
- Collect rel types with [rel IN r | type(rel)].
- Person, Company, Intermediary, Address share no common label — do not write
  `MATCH (e:Entity)`. Query each label explicitly or use `MATCH (n) WHERE n.node_id = $id`.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────

class RiskVerdict(StrEnum):
    HIGH_RISK   = "HIGH_RISK"
    MEDIUM_RISK = "MEDIUM_RISK"
    LOW_RISK    = "LOW_RISK"
    CLEARED     = "CLEARED"


VERDICT_PRIORITY: dict[str, int] = {
    "HIGH_RISK":   3,
    "MEDIUM_RISK": 2,
    "LOW_RISK":    1,
    "CLEARED":     0,
}


class Severity(StrEnum):
    HIGH   = "HIGH"
    MEDIUM = "MEDIUM"
    LOW    = "LOW"
    INFO   = "INFO"


SEV_ORDER: dict[str, int] = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INFO": 3}


# ─────────────────────────────────────────────────────────────────────────────
# Anomaly Pattern
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AnomalyPattern:
    description: str
    severity: str
    cypher: str
    id_key: str
    params: dict[str, Any] = field(default_factory=dict)
    typology_id: str = ""
    entity_label: str = ""
    entity_node_alias: str = ""
    entity_id_field: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Anomaly Registry
# All Cypher validated against the live Layer 1 graph (19 Person, 131 Company,
# 7 Intermediary, 28 Address, 3 Jurisdiction nodes).
# ─────────────────────────────────────────────────────────────────────────────

ANOMALY_REGISTRY: dict[str, AnomalyPattern] = {

    "common_controller_across_shells": AnomalyPattern(
        description=(
            "A single natural person holds officer/director roles across multiple "
            "offshore shell companies. Suggests a centrally-controlled opacity "
            "structure (FATF Recommendation 24 — beneficial ownership)."
        ),
        severity=Severity.HIGH,
        id_key="person_id",
        entity_label="Person",
        entity_node_alias="p",
        entity_id_field="node_id",
        params={"min_shell_count": 3},
        typology_id="MAS-626-8",
        cypher="""
MATCH (p:Person)-[:IS_OFFICER_OF]->(c:Company)
WITH p,
     count(c)                          AS shell_count,
     collect(c.name)[0..10]            AS shell_names,
     collect(DISTINCT c.jurisdiction)  AS jurisdictions
WHERE shell_count >= $min_shell_count
RETURN p.node_id        AS person_id,
       p.name           AS person_name,
       p.countries      AS countries,
       shell_count,
       shell_names,
       jurisdictions
ORDER BY shell_count DESC
LIMIT 20
""",
    ),

    "layered_ownership": AnomalyPattern(
        description=(
            "Multi-hop connection from a Person to a target Company through "
            "a chain of intermediary officerships or address-sharing relations. "
            "Obscures the true beneficial owner (FATF Rec. 24-25)."
        ),
        severity=Severity.HIGH,
        id_key="target_company_id",
        entity_label="Company",
        entity_node_alias="target",
        entity_id_field="node_id",
        params={"max_depth": 4},
        typology_id="MAS-626-6",
        cypher="""
MATCH path = (p:Person)-[:IS_OFFICER_OF|SHARES_ADDRESS_WITH*2..4]-(target:Company)
WITH p,
     target,
     path,
     [r IN relationships(path) | type(r)] AS hop_types,
     size(relationships(path))             AS chain_depth
WHERE chain_depth >= 2
RETURN p.node_id       AS ultimate_person_id,
       p.name          AS ultimate_person_name,
       target.node_id  AS target_company_id,
       target.name     AS target_company_name,
       chain_depth,
       hop_types
ORDER BY chain_depth DESC, p.name
LIMIT 30
""",
    ),

    "high_risk_jurisdiction": AnomalyPattern(
        description=(
            "Company registered in a jurisdiction rated `high` for AML risk — "
            "BVI, Panama, Bahamas, Seychelles, and similar offshore havens. "
            "Triggers enhanced due diligence under MAS Notice 626 paragraph 4.1(b)."
        ),
        severity=Severity.HIGH,
        id_key="company_id",
        entity_label="Company",
        entity_node_alias="c",
        entity_id_field="node_id",
        typology_id="MAS-626-4",
        cypher="""
MATCH (c:Company)-[:INCORPORATED_IN]->(j:Jurisdiction)
WHERE j.aml_risk_rating = 'high'
RETURN c.node_id           AS company_id,
       c.name              AS company_name,
       c.jurisdiction      AS jurisdiction_code,
       j.name              AS jurisdiction_name,
       j.aml_risk_rating   AS risk_rating,
       c.service_provider  AS service_provider
ORDER BY c.name
LIMIT 30
""",
    ),

    "shared_address_cluster": AnomalyPattern(
        description=(
            "Multiple distinct Companies share a single registered address in "
            "a cluster small enough (2-8) to be a beneficial-ownership signal "
            "rather than a corporate-services building. Classic shell indicator."
        ),
        severity=Severity.HIGH,
        id_key="address_id",
        entity_label="Address",
        entity_node_alias="a",
        entity_id_field="node_id",
        typology_id="MAS-626-6",
        cypher="""
MATCH (c:Company)-[:REGISTERED_AT]->(a:Address)
WITH a,
     count(DISTINCT c)             AS company_count,
     collect(DISTINCT c.name)[0..10] AS companies
WHERE company_count >= 2 AND company_count <= 8
RETURN a.node_id         AS address_id,
       a.address         AS address_text,
       company_count,
       companies
ORDER BY company_count DESC
LIMIT 20
""",
    ),

    "intermediary_shell_network": AnomalyPattern(
        description=(
            "An Intermediary (law firm / registered agent) has set up a large "
            "number of Companies incorporated in high-risk jurisdictions — a "
            "pattern that characterised the Panama Papers Mossack Fonseca cohort."
        ),
        severity=Severity.MEDIUM,
        id_key="intermediary_id",
        entity_label="Intermediary",
        entity_node_alias="i",
        entity_id_field="node_id",
        params={"min_shell_count": 5},
        typology_id="MAS-626-6",
        cypher="""
MATCH (i:Intermediary)-[:INTERMEDIARY_OF]->(c:Company)-[:INCORPORATED_IN]->(j:Jurisdiction)
WHERE j.aml_risk_rating = 'high'
WITH i,
     count(DISTINCT c)                      AS shell_count,
     collect(DISTINCT j.name)[0..5]         AS jurisdictions,
     collect(DISTINCT c.name)[0..10]        AS sample_companies
WHERE shell_count >= $min_shell_count
RETURN i.node_id          AS intermediary_id,
       i.name             AS intermediary_name,
       i.countries        AS intermediary_country,
       shell_count,
       jurisdictions,
       sample_companies
ORDER BY shell_count DESC
LIMIT 15
""",
    ),

    "bearer_obscured_ownership": AnomalyPattern(
        description=(
            "Company records a nominee or bearer-style officer instead of a "
            "named natural person — names like 'THE BEARER', a nominee-services "
            "firm, or a trustee entity. Indicates deliberate opacity of "
            "beneficial ownership."
        ),
        severity=Severity.HIGH,
        id_key="company_id",
        entity_label="Company",
        entity_node_alias="c",
        entity_id_field="node_id",
        typology_id="MAS-626-8",
        cypher="""
MATCH (p:Person)-[:IS_OFFICER_OF]->(c:Company)
WHERE toUpper(p.name) CONTAINS 'BEARER'
   OR toUpper(p.name) CONTAINS 'NOMINEE'
   OR toUpper(p.name) CONTAINS 'TRUSTEE'
RETURN c.node_id          AS company_id,
       c.name             AS company_name,
       p.name             AS nominee_name,
       c.jurisdiction     AS jurisdiction
ORDER BY c.name
LIMIT 20
""",
    ),
}


TYPOLOGY_TO_PATTERN: dict[str, str] = {
    pat.typology_id: name
    for name, pat in ANOMALY_REGISTRY.items()
    if pat.typology_id
}

# Map Neo4j node label → applicable anomaly patterns. ICIJ node_ids have no
# prefix we can use, so the dispatcher looks up the node's label first.
ENTITY_TO_PATTERNS: dict[str, list[str]] = {
    "Person":       ["common_controller_across_shells", "layered_ownership"],
    "Company":      ["high_risk_jurisdiction", "shared_address_cluster",
                     "bearer_obscured_ownership", "layered_ownership"],
    "Intermediary": ["intermediary_shell_network"],
    "Address":      ["shared_address_cluster"],
    "Jurisdiction": ["high_risk_jurisdiction"],
}

PATTERN_HINTS: str = "\n".join(
    f"    '{name}' — {p.description.split('.')[0]}."
    for name, p in ANOMALY_REGISTRY.items()
)


# ─────────────────────────────────────────────────────────────────────────────
# Dataclasses
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AMLRiskResponse:
    """Top-level response returned by AMLAgent to the chat UI."""
    session_id: str
    question: str
    answer: str
    verdict: str = RiskVerdict.CLEARED
    risk_score: float = 0.0
    entity_id: str = ""
    findings: list[dict] = field(default_factory=list)
    triggered_typologies: list[str] = field(default_factory=list)
    cited_sections: list[dict] = field(default_factory=list)
    cited_chunks: list[dict] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return self.__dict__.copy()
