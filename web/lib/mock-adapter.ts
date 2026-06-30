import type { AgentTranscriptEvent, CaseAssessment, DeepStatus } from "./types";
import nielsen from "@/mocks/nielsen-enterprises.json";

const PRESET_ANSWERS: Record<string, CaseAssessment> = {
  nielsen: nielsen as CaseAssessment,
};

function pickPreset(question: string): CaseAssessment {
  const q = question.toLowerCase();
  if (q.includes("nescoll") || q.includes("hangon") || q.includes("nielsen") || q.includes("mossack") || q.includes("jonathan") || q.includes("bsi")) {
    return PRESET_ANSWERS.nielsen;
  }
  return PRESET_ANSWERS.nielsen;
}

export async function mockInvestigate(question: string): Promise<CaseAssessment> {
  await new Promise((r) => setTimeout(r, 400));
  const payload = pickPreset(question);
  return { ...payload, question };
}

// Mock job state. One in-flight "job" at a time is enough for the demo.
type MockJob = {
  jobId: string;
  question: string;
  startedAt: number;
  cancelled: boolean;
};
const MOCK_PHASES = [
  "Resolving entity from question…",
  "Traversing 2-hop entity subgraph…",
  "Detecting graph anomaly patterns…",
  "Retrieving MAS Notice 626 typology chunks…",
  "Synthesising verdict…",
];
const MOCK_PHASE_MS = 2500;
const MOCK_TOTAL_MS = MOCK_PHASES.length * MOCK_PHASE_MS;
const _mockJobs: Map<string, MockJob> = new Map();

// Per-phase fake agent transcript events — surfaced cumulatively as the
// mock job advances, so offline mode exercises the same AgentTranscript
// component the real backend will drive.
const MOCK_AGENT_EVENTS_BY_PHASE: AgentTranscriptEvent[][] = [
  // phase 0 — setup / plan
  [
    {
      id: "h2ogpte-mock-plan",
      kind: "agent_analysis",
      turn_idx: -1,
      title: "Agent reasoning",
      message:
        "I'll investigate Nielsen Enterprises Limited by following the AML investigation workflow: " +
        "(1) traverse the 2-hop entity subgraph, (2) detect anomaly patterns over the resulting subgraph, " +
        "(3) retrieve MAS-626 typology chunks for matched patterns, then synthesise a verdict.",
      code: null,
      files: [],
      timestamp: "",
    },
  ],
  // phase 1 — traverse
  [
    {
      id: "h2ogpte-mock-turn-0",
      kind: "turn",
      turn_idx: 0,
      title: "Step 1 — traverse_entity_network",
      message:
        "Calling the MCP tool with entity_id=10122953 (Nielsen Enterprises Limited) depth=2. " +
        "Returned 14 nodes (4 Companies, 6 Persons, 2 Addresses, 2 Intermediaries) and 27 edges.",
      code:
        "from aml_guard_mcp import traverse_entity_network\n\n" +
        "result = traverse_entity_network(entity_id='10122953', entity_type='Company', depth=2)\n" +
        "print(f'nodes={len(result[\"nodes\"])} edges={len(result[\"edges\"])}')",
      files: ["step1_traverse.py", "step1_traverse.pdf"],
      timestamp: "",
    },
  ],
  // phase 2 — anomalies
  [
    {
      id: "h2ogpte-mock-turn-1",
      kind: "turn",
      turn_idx: 1,
      title: "Step 2 — detect_graph_anomalies",
      message:
        "Detected 3 anomaly patterns over the subgraph. common_controller_across_shells: HIGH " +
        "(3 shells, 1 controller). layered_ownership: HIGH (4-layer chain). " +
        "shared_address_cluster: MEDIUM (2 entities at Geneva address).",
      code:
        "from aml_guard_mcp import detect_graph_anomalies\n\n" +
        "result = detect_graph_anomalies(\n" +
        "  pattern_names=['common_controller_across_shells', 'layered_ownership',\n" +
        "                 'shared_address_cluster', 'intermediary_shell_network'],\n" +
        "  entity_id='10122953')",
      files: ["step2_detect_anomalies.py", "step2_detect_anomalies.pdf"],
      timestamp: "",
    },
  ],
  // phase 3 — typology
  [
    {
      id: "h2ogpte-mock-turn-2",
      kind: "turn",
      turn_idx: 2,
      title: "Step 3 — retrieve_typology_chunks",
      message:
        "Retrieved 5 typology citations from MAS Notice 626 and FATF. " +
        "Top hit (sim 0.87): MAS Notice 626 §6.4 — Enhanced due diligence required where beneficial " +
        "ownership is concentrated through multiple intermediary entities.",
      code:
        "from aml_guard_mcp import retrieve_typology_chunks\n\n" +
        "chunks = retrieve_typology_chunks(\n" +
        "  query_text='common controller across shell companies layered ownership',\n" +
        "  top_k=5)",
      files: ["step3_typology.py", "step3_typology.pdf"],
      timestamp: "",
    },
  ],
  // phase 4 — synthesis + final
  [
    {
      id: "h2ogpte-mock-turn-3",
      kind: "turn",
      turn_idx: 3,
      title: "AML Risk Assessment — Nielsen Enterprises Limited",
      message:
        "All three evidence-gathering steps complete. Synthesising the final verdict: HIGH_RISK at " +
        "score 0.82 driven by ownership-opacity signals concentrated around the registered " +
        "intermediary, with regulatory backing in MAS Notice 626 §6.4 and FATF Recommendation 24.",
      code: null,
      files: ["risk_pie.svg", "risk_pie.png", "subgraph.svg", "subgraph.png"],
      timestamp: "",
    },
    {
      id: "h2ogpte-mock-final",
      kind: "final_summary",
      turn_idx: 999,
      title: "Run summary",
      message: "12.5 seconds · model=claude-sonnet-4-6 · in_tok=15570 · out_tok=4220 · cost=$0.41",
      code: null,
      files: [],
      timestamp: "",
    },
  ],
];

export async function mockStartDeep(question: string): Promise<{ job_id: string; case: CaseAssessment }> {
  await new Promise((r) => setTimeout(r, 200));
  const payload = pickPreset(question);
  const jobId = `mock-${Date.now()}`;
  _mockJobs.set(jobId, {
    jobId,
    question,
    startedAt: Date.now(),
    cancelled: false,
  });
  return { job_id: jobId, case: { ...payload, question } };
}

export async function mockGetDeepStatus(jobId: string): Promise<DeepStatus> {
  await new Promise((r) => setTimeout(r, 120));
  const job = _mockJobs.get(jobId);
  if (!job) {
    return {
      status: "error",
      phase_idx: 0,
      phase_label: "unknown job",
      elapsed_seconds: 0,
      input_tokens: null,
      output_tokens: null,
      agent_events: [],
      result: null,
      error: "Unknown job id",
    };
  }
  const elapsed = Date.now() - job.startedAt;
  const elapsedSec = Math.floor(elapsed / 1000);
  if (job.cancelled) {
    return {
      status: "cancelled",
      phase_idx: 0,
      phase_label: "Cancelled by user",
      elapsed_seconds: elapsedSec,
      input_tokens: null,
      output_tokens: null,
      agent_events: mockAgentEventsThrough(elapsed),
      result: null,
      error: null,
    };
  }
  if (elapsed >= MOCK_TOTAL_MS) {
    const payload = pickPreset(job.question);
    return {
      status: "done",
      phase_idx: MOCK_PHASES.length - 1,
      phase_label: "Done",
      elapsed_seconds: elapsedSec,
      input_tokens: 12450,
      output_tokens: 3120,
      agent_events: mockAgentEventsThrough(MOCK_TOTAL_MS),
      result: {
        ...payload,
        question: job.question,
        summary:
          "Agent confirmed three high-severity ownership-opacity signals concentrated " +
          "around the subject's registered intermediary. Cross-referenced against MAS " +
          "Notice 626 §6 and FATF Recommendation 24; pattern signature is consistent " +
          "with intermediary-led shell layering.",
        recommended_actions: [
          "Escalate to MLRO for STR pre-filing review within 24 hours.",
          "Freeze new account-opening eligibility pending UBO re-verification.",
          "Request beneficial-ownership documentation directly from the intermediary.",
        ],
      },
      error: null,
    };
  }
  const phaseIdx = Math.min(
    MOCK_PHASES.length - 1,
    Math.floor(elapsed / MOCK_PHASE_MS),
  );
  return {
    status: "running",
    phase_idx: phaseIdx,
    phase_label: MOCK_PHASES[phaseIdx],
    elapsed_seconds: elapsedSec,
    input_tokens: phaseIdx >= 3 ? 8200 + phaseIdx * 1500 : null,
    output_tokens: phaseIdx >= 3 ? 1100 + phaseIdx * 400 : null,
    agent_events: mockAgentEventsThrough(elapsed),
    result: null,
    error: null,
  };
}

function mockAgentEventsThrough(elapsedMs: number): AgentTranscriptEvent[] {
  // Reveal each phase's events once that phase has been entered. Stamp the
  // timestamp with "now" so the AgentTranscript reveal animation runs.
  const phaseIdx = Math.min(
    MOCK_AGENT_EVENTS_BY_PHASE.length - 1,
    Math.floor(elapsedMs / MOCK_PHASE_MS),
  );
  const out: AgentTranscriptEvent[] = [];
  const nowIso = new Date().toISOString();
  for (let i = 0; i <= phaseIdx; i++) {
    for (const ev of MOCK_AGENT_EVENTS_BY_PHASE[i]) {
      out.push({ ...ev, timestamp: ev.timestamp || nowIso });
    }
  }
  return out;
}

export async function mockCancelDeep(jobId: string): Promise<void> {
  const job = _mockJobs.get(jobId);
  if (job) job.cancelled = true;
}
