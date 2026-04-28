/**
 * Shared API contract between the AML Guard frontend and the teammate's backend.
 * Aligned with src/mcp/schema.py (Severity + RiskVerdict) and src/mcp/tool_defs.py.
 *
 * Hand this file to the teammate — they return this shape from POST /api/investigate.
 */

export type Verdict = "HIGH_RISK" | "MEDIUM_RISK" | "LOW_RISK" | "CLEARED";

export type Severity = "HIGH" | "MEDIUM" | "LOW" | "INFO";

export type ToolName =
  | "traverse_entity_network"
  | "detect_graph_anomalies"
  | "retrieve_typology_chunks"
  | "trace_evidence";

export type PatternName =
  | "transaction_structuring"
  | "high_risk_jurisdiction"
  | "shared_address_cluster"
  | "intermediary_shell_network"
  | "common_controller_across_shells"
  | "layered_ownership"
  | "bearer_obscured_ownership";

export interface Finding {
  id: string;
  pattern_name: PatternName | string;
  severity: Severity;
  score: number;                 // 0–10, UI only
  description: string;
  evidence_ids: string[];        // TypologyChunk.id refs
}

export interface TypologyChunk {
  id: string;
  source: "FATF" | "MAS Notice 626";
  section: string;               // e.g. "para 6.4"
  title: string;                 // human-readable section title
  text: string;                  // sentence-bounded snippet (~350 chars)
  text_full?: string;            // full paragraph text, for "Show more" expansion
  similarity_score: number;      // 0–1
}

export interface InvestigationStep {
  tool: ToolName;
  summary: string;
  cypher_used?: string;
  cited_sections?: string[];
  cited_chunks?: string[];
  timestamp: string;             // ISO
}

export interface SubgraphNode {
  id: string;
  label: string;
  type: "Person" | "Company" | "Intermediary" | "Address" | "Jurisdiction";
  risk_tier?: "HIGH" | "MEDIUM" | "LOW";
  note?: string;                 // e.g. "BVI", "Mossack Fonseca", "Geneva"
}

export interface SubgraphEdge {
  source: string;
  target: string;
  kind: string;                  // IS_OFFICER_OF, INTERMEDIARY_OF, REGISTERED_AT, ...
}

export interface CaseAssessment {
  case_id: string;               // e.g. "STR-2026-0417-001"
  subject: {
    id: string;
    name: string;
    type: "Person" | "Company";
    jurisdiction: string;        // ISO alpha-3 ("VGB") or human ("BVI")
    profile_snippet: string;
  };
  question: string;
  verdict: Verdict;
  risk_score: number;            // 0–1
  headline: string;              // one-line rationale for the VerdictBanner
  tx_velocity: number[];         // 6–12 ints for the Sparkline
  findings: Finding[];
  typology_chunks: TypologyChunk[];
  investigation_steps: InvestigationStep[];
  subgraph: { nodes: SubgraphNode[]; edges: SubgraphEdge[] };
  created_at: string;            // ISO
}
