"""
Shared schema, dataclasses, and anomaly registry for AML Guard.

Provides:
  GRAPH_SCHEMA_HINT  — injected into Claude's system prompt (update as Layer 1 is built)
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
# TODO: update this block as your teammate loads Layer 1 data.
#       Keep it accurate — Claude uses it to generate valid Cypher without
#       calling get-neo4j-schema on every turn.
# ─────────────────────────────────────────────────────────────────────────────

GRAPH_SCHEMA_HINT = """
## Neo4j Graph Schema — AML Guard

### LAYER 1 — AML Entity Graph

TODO: Fill in node labels, properties, and relationships once your teammate
      has finalised the data model and loaded the CSVs into Neo4j.

Example structure to document here:

Node: Entity
  Properties: entity_id (str, unique), name (str), type (str: individual|corporate),
              risk_tier (str: high|medium|low), is_pep (bool), sanctions_match (bool),
              kyc_status (str: verified|pending|failed), country (str)

Node: Account
  Properties: account_id (str, unique), entity_id (str), account_type (str),
              currency (str), country (str), opened_date (date), status (str),
              average_monthly_balance (float)

Node: Transaction
  Properties: transaction_id (str, unique), from_account_id (str),
              to_account_id (str), amount (float), currency (str),
              date (date), type (str), flagged_suspicious (bool),
              country_of_origin (str), country_of_destination (str)

Node: Alert
  Properties: alert_id (str, unique), entity_id (str), alert_type (str),
              severity (str: HIGH|MEDIUM|LOW), status (str: open|closed|escalated),
              created_at (datetime), description (str)

Node: Jurisdiction
  Properties: jurisdiction_id (str, unique), name (str), country (str),
              fatf_status (str: member|non-member|blacklist|greylist),
              aml_risk_rating (str: low|medium|high)

### LAYER 1 Relationships (TODO: update)

(Entity)-[:HAS_ACCOUNT]->(Account)
(Transaction)-[:FROM_ACCOUNT]->(Account)
(Transaction)-[:TO_ACCOUNT]->(Account)
(Entity)-[:OWNS]->(Entity)
(Entity)-[:REGISTERED_IN]->(Jurisdiction)
(Entity)-[:RESIDES_IN]->(Jurisdiction)
(Alert)-[:RELATES_TO]->(Entity)

### LAYER 2 — Typology Documents

Node: Typology  (replaces Regulation from loanguard-ai)
  Properties: typology_id (str), name (str), issuing_body (str: FATF|AUSTRAC),
              document_type (str), effective_date (date)

Node: Section
  Properties: section_id (str), typology_id (str), title (str), text (str)

Node: Indicator  (replaces Requirement — red flag indicators, not thresholds)
  Properties: indicator_id (str), section_id (str), description (str),
              indicator_type (str: behavioral|structural|transactional),
              severity (str: HIGH|MEDIUM|LOW)

Node: Chunk
  Properties: chunk_id (str), section_id (str), text (str),
              token_count (int), chunk_index (int),
              embedding (list[float] — 1536 dims, OpenAI text-embedding-3-small)

### LAYER 2 Relationships

(Typology)-[:APPLIES_TO_JURISDICTION]->(Jurisdiction)
(Typology)-[:HAS_SECTION]->(Section)
(Section)-[:HAS_INDICATOR]->(Indicator)
(Section)-[:HAS_CHUNK]->(Chunk)
(Chunk)-[:NEXT_CHUNK]->(Chunk)
(Chunk)-[:SEMANTICALLY_SIMILAR {score}]->(Chunk)

### LAYER 3 — Case Assessments (runtime, written by agent)

Node: CaseAssessment
  Properties: assessment_id (str, unique), entity_id (str), entity_type (str),
              verdict (str: HIGH_RISK|MEDIUM_RISK|LOW_RISK|CLEARED),
              risk_score (float 0-1), agent (str), created_at (datetime)

Node: RiskFinding
  Properties: finding_id (str), finding_type (str), severity (str: HIGH|MEDIUM|LOW|INFO),
              description (str), pattern_name (str|null)

Node: InvestigationStep
  Properties: step_id (str), step_number (int), description (str),
              cypher_used (str|null)

### LAYER 3 Relationships

(Entity)-[:HAS_ASSESSMENT]->(CaseAssessment)
(CaseAssessment)-[:HAS_FINDING]->(RiskFinding)
(CaseAssessment)-[:HAS_STEP]->(InvestigationStep)
(InvestigationStep)-[:CITES_TYPOLOGY]->(Section)
(InvestigationStep)-[:CITES_CHUNK {similarity_score}]->(Chunk)

### Cypher Best Practices
- Always use parameterised queries ($param) — never string interpolation.
- For variable-length paths use size(r) not length(r).
- Collect rel types with [rel IN r | type(rel)].
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
# TODO: replace placeholder Cypher with queries that match your Layer 1 schema.
#       Each pattern's Cypher should be validated against a live Neo4j instance
#       before being committed here.
# ─────────────────────────────────────────────────────────────────────────────

ANOMALY_REGISTRY: dict[str, AnomalyPattern] = {

    "transaction_structuring": AnomalyPattern(
        description=(
            "Multiple sub-threshold cash transactions flowing into the same account "
            "from distinct sources, consistent with structuring to avoid AUSTRAC "
            "threshold transaction reporting (TTR) obligations."
        ),
        severity=Severity.HIGH,
        id_key="target_account_id",
        entity_label="Account",
        entity_node_alias="target",
        entity_id_field="account_id",
        # TODO: update Cypher to match your Account + Transaction schema.
        cypher="""
MATCH (t:Transaction)-[:TO_ACCOUNT]->(target:Account)
WHERE t.flagged_suspicious = true
  AND t.amount < 10000
WITH target,
     count(t)                                     AS tx_count,
     sum(t.amount)                                AS total_amount,
     collect(DISTINCT t.from_account_id)[0..10]   AS source_accounts,
     collect(t.transaction_id)[0..10]             AS sample_txn_ids,
     min(t.date)                                  AS earliest,
     max(t.date)                                  AS latest
WHERE tx_count >= 3
RETURN target.account_id   AS target_account_id,
       tx_count,
       round(total_amount) AS total_amount,
       source_accounts,
       sample_txn_ids,
       earliest,
       latest
ORDER BY tx_count DESC
LIMIT 20
""",
    ),

    "rapid_fund_movement": AnomalyPattern(
        description=(
            "Funds received into an account and moved out again within 48 hours "
            "with little or no residual balance. Consistent with pass-through "
            "or layering typologies."
        ),
        severity=Severity.HIGH,
        id_key="account_id",
        entity_label="Account",
        entity_node_alias="a",
        entity_id_field="account_id",
        # TODO: implement once Transaction date fields and account schema are confirmed.
        cypher="""
// TODO: implement rapid_fund_movement Cypher
// Suggested approach: find accounts where inbound and outbound transactions
// occur within duration.inDays(t_in.date, t_out.date) <= 2
RETURN 'rapid_fund_movement pattern not yet implemented' AS status
LIMIT 1
""",
    ),

    "layered_ownership": AnomalyPattern(
        description=(
            "Multi-hop OWNS chains (depth >= 2) obscuring the true beneficial "
            "owner of an entity. Consistent with FATF Recommendation 24 "
            "beneficial ownership opacity typology."
        ),
        severity=Severity.HIGH,
        id_key="ultimate_owner_id",
        entity_label="Entity",
        entity_node_alias="owner",
        entity_id_field="entity_id",
        # TODO: update node label from Borrower → Entity once Layer 1 is loaded.
        cypher="""
MATCH path = (owner:Entity)-[:OWNS*2..]->(subsidiary:Entity)
WITH owner,
     subsidiary,
     length(path)                                         AS chain_depth,
     [n IN nodes(path) | n.entity_id]                    AS ownership_chain
WHERE chain_depth >= 2
RETURN owner.entity_id    AS ultimate_owner_id,
       owner.name         AS owner_name,
       subsidiary.entity_id AS subsidiary_id,
       subsidiary.name    AS subsidiary_name,
       chain_depth,
       ownership_chain
ORDER BY chain_depth DESC
LIMIT 30
""",
    ),

    "high_risk_jurisdiction": AnomalyPattern(
        description=(
            "Entities registered in or transacting with jurisdictions on the "
            "FATF blacklist or greylist, or with aml_risk_rating = 'high'. "
            "Requires enhanced due diligence per FATF Recommendation 19."
        ),
        severity=Severity.HIGH,
        id_key="entity_id",
        entity_label="Entity",
        entity_node_alias="e",
        entity_id_field="entity_id",
        # TODO: update to match your Jurisdiction node and relationship names.
        cypher="""
MATCH (e:Entity)-[:REGISTERED_IN|RESIDES_IN]->(j:Jurisdiction)
WHERE j.aml_risk_rating = 'high'
   OR j.fatf_status IN ['blacklist', 'greylist']
RETURN e.entity_id        AS entity_id,
       e.name             AS name,
       j.jurisdiction_id  AS jurisdiction_id,
       j.name             AS jurisdiction_name,
       j.aml_risk_rating  AS aml_risk_rating,
       j.fatf_status      AS fatf_status
ORDER BY j.aml_risk_rating DESC, e.entity_id
LIMIT 30
""",
    ),

    "pep_association": AnomalyPattern(
        description=(
            "Entity is a politically exposed person (PEP) or is directly "
            "associated with a PEP via ownership or directorship. "
            "Triggers enhanced due diligence per FATF Recommendation 12."
        ),
        severity=Severity.HIGH,
        id_key="entity_id",
        entity_label="Entity",
        entity_node_alias="e",
        entity_id_field="entity_id",
        # TODO: update once is_pep field and relationship schema are confirmed.
        cypher="""
MATCH (e:Entity)
WHERE e.is_pep = true
   OR e.sanctions_match = true
RETURN e.entity_id  AS entity_id,
       e.name       AS name,
       e.is_pep     AS is_pep,
       e.sanctions_match AS sanctions_match
ORDER BY e.entity_id
LIMIT 30
""",
    ),

    "smurfing": AnomalyPattern(
        description=(
            "Multiple low-value cash deposits across different accounts "
            "that aggregate to a significant sum — classic smurfing / "
            "structuring typology to avoid threshold reporting."
        ),
        severity=Severity.HIGH,
        id_key="entity_id",
        entity_label="Entity",
        entity_node_alias="e",
        entity_id_field="entity_id",
        # TODO: implement once transaction aggregation by entity is confirmed.
        cypher="""
// TODO: implement smurfing Cypher
// Suggested approach: aggregate sub-$10k deposits across all accounts
// owned by the same entity within a rolling 30-day window.
RETURN 'smurfing pattern not yet implemented' AS status
LIMIT 1
""",
    ),
}


TYPOLOGY_TO_PATTERN: dict[str, str] = {
    pat.typology_id: name
    for name, pat in ANOMALY_REGISTRY.items()
    if pat.typology_id
}

# Map entity ID prefix → applicable patterns (update prefixes to match your data).
ENTITY_TO_PATTERNS: dict[str, list[str]] = {
    "ENT":   list(ANOMALY_REGISTRY.keys()),
    "ACCT":  ["transaction_structuring", "rapid_fund_movement"],
    "TXN":   ["transaction_structuring", "rapid_fund_movement", "smurfing"],
    "ALERT": list(ANOMALY_REGISTRY.keys()),
}

PATTERN_HINTS: str = "\n".join(
    f"    '{name}' — {p.description.split('.')[0]}."
    for name, p in ANOMALY_REGISTRY.items()
)


# ─────────────────────────────────────────────────────────────────────────────
# Dataclasses
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RiskFinding:
    finding_type: str
    severity: str
    description: str
    pattern_name: str = ""
    entity_ids: list[str] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return self.__dict__.copy()


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
    assessment_id: str | None = None

    def to_dict(self) -> dict:
        return self.__dict__.copy()
