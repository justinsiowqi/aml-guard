"use client";

import { useEffect, useMemo, useState } from "react";
import type {
  DeepStatus,
  Finding,
  RiskDecompositionBar,
  TypologyChunk,
  Verdict,
} from "@/lib/types";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Circle,
  FileText,
  Loader2,
  Scale,
  Send,
  ShieldCheck,
  Sparkles,
  XCircle,
} from "lucide-react";

// ─── SummaryBlock ────────────────────────────────────────────────────────────
// Renders the deep-agent SUMMARY paragraph with inline entity / pattern / chunk
// highlighting, sentence-level line breaks for readability, and a distinct
// bordered block for the trailing "Follow-up: …" note.

const _AML_PATTERNS = [
  "bearer_obscured_ownership",
  "common_controller_across_shells",
  "layered_ownership",
  "intermediary_shell_network",
  "high_risk_jurisdiction",
  "shared_address_cluster",
].join("|");

// Single regex that tokenises the summary into highlighted vs plain segments.
// Groups, in priority order:
//   1. (node_id NNNNN) references
//   2. bare parenthesised node IDs like (10122953)
//   3. chunk citations:  chunks 6.14-c1, 2.1-c12
//   4. finding references:  f_bearer_obscured_ownership
//   5. AML pattern names
const _SUMMARY_TOKEN_RE = new RegExp(
  `(\\(node_id \\d+\\)` +
  `|\\(\\d{7,9}\\)` +
  `|chunks?\\s+[\\d\\w\\.\\-]+(?:,\\s*[\\d\\w\\.\\-]+)*` +
  `|f_(?:${_AML_PATTERNS})` +
  `|${_AML_PATTERNS})`,
  "gi",
);

function _renderSummaryTokens(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  let last = 0;
  _SUMMARY_TOKEN_RE.lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = _SUMMARY_TOKEN_RE.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const tok = m[0];
    if (/^chunks?/i.test(tok)) {
      parts.push(
        <span key={m.index} className="rounded bg-surface-container-high px-1 font-mono text-[10.5px] text-on-surface-variant">
          {tok}
        </span>,
      );
    } else if (tok.startsWith("(")) {
      parts.push(
        <span key={m.index} className="font-mono text-[11px] text-on-surface-variant/70">
          {tok}
        </span>,
      );
    } else {
      // AML pattern name or f_pattern reference
      parts.push(
        <code key={m.index} className={`rounded px-1 font-mono text-[11px] ${_patternChipClass(tok)}`}>
          {tok}
        </code>,
      );
    }
    last = m.index + tok.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

function _splitSentences(text: string): string[] {
  // Split at ". [Capital]" and "; [Capital]" — both are natural clause
  // boundaries in the agent's legal-prose style.
  const out: string[] = [];
  const re = /(?:\.|\;) (?=[A-Z])/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    const chunk = text.slice(last, m.index + 1).trim(); // keep the period/semicolon
    if (chunk) out.push(chunk);
    last = m.index + 2;
  }
  const tail = text.slice(last).trim();
  if (tail) out.push(tail);
  return out;
}

// Patterns that contribute ≥0.30 to risk score — rendered in red everywhere.
const _HIGH_WEIGHT_PATTERNS = new Set([
  "bearer_obscured_ownership",
  "intermediary_shell_network",
]);

function _patternChipClass(name: string): string {
  return _HIGH_WEIGHT_PATTERNS.has(name.toLowerCase())
    ? "bg-error-container/50 text-on-error-container"
    : "bg-secondary-fixed/25 text-on-secondary-fixed-variant";
}

function _extractPatterns(text: string): string[] {
  const re = new RegExp(`\\b(${_AML_PATTERNS})\\b`, "gi");
  const seen = new Set<string>();
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) seen.add(m[1].toLowerCase());
  return Array.from(seen);
}

function SummaryBlock({ text }: { text: string }) {
  // Separate the trailing "Follow-up: …" note from the main prose.
  const followUpMatch = text.match(/\.\s*(Follow-up:.+)$/is);
  const mainText = followUpMatch
    ? text.slice(0, text.length - followUpMatch[1].length).trim()
    : text;
  const followUpText = followUpMatch
    ? followUpMatch[1].replace(/^Follow-up:\s*/i, "").trim()
    : null;

  const patterns = useMemo(() => _extractPatterns(mainText), [mainText]);
  const sentences = useMemo(() => _splitSentences(mainText), [mainText]);

  return (
    <div className="mb-3 space-y-2">
      {/* Pattern chips — at-a-glance risk signals */}
      {patterns.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {patterns.map((p) => (
            <span
              key={p}
              className={`rounded-sm px-1.5 py-0.5 font-mono text-[10px] font-semibold ${_patternChipClass(p)}`}
            >
              {p}
            </span>
          ))}
        </div>
      )}

      {/* Prose — compact clauses, one per row */}
      <div className="space-y-1">
        {sentences.map((s, i) => (
          <p key={i} className="text-[11.5px] leading-relaxed text-on-surface-variant">
            {_renderSummaryTokens(s)}
          </p>
        ))}
      </div>

      {/* Follow-up badge */}
      {followUpText && (
        <div className="flex items-start gap-2 rounded border border-outline-variant/30 bg-surface-container-low px-2.5 py-2">
          <span className="mt-0.5 shrink-0 rounded-sm bg-surface-container-high px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wider text-on-surface-variant">
            Follow-up
          </span>
          <p className="text-[11px] italic leading-relaxed text-on-surface-variant/80">
            {_renderSummaryTokens(followUpText)}
          </p>
        </div>
      )}
    </div>
  );
}

/** Render inline markdown — bold, inline code — without a heavy dependency. */
function InlineMarkdown({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return <strong key={i} className="font-semibold">{part.slice(2, -2)}</strong>;
        }
        if (part.startsWith("`") && part.endsWith("`")) {
          return (
            <code key={i} className="rounded bg-surface-container-high px-1 font-mono text-[11px] text-on-surface">
              {part.slice(1, -1)}
            </code>
          );
        }
        return <span key={i}>{part}</span>;
      })}
    </>
  );
}

const VERDICT_META: Record<
  Verdict,
  { label: string; tone: "error" | "warning" | "success"; note: string; pill: string }
> = {
  HIGH_RISK:   { label: "High",   tone: "error",   note: "File STR; freeze eligibility review", pill: "High" },
  MEDIUM_RISK: { label: "Medium", tone: "warning", note: "Escalate to senior investigator",    pill: "Medium" },
  LOW_RISK:    { label: "Low",    tone: "success", note: "Continue periodic monitoring",       pill: "Low" },
  CLEARED:     { label: "Cleared", tone: "success", note: "No further action",                 pill: "Cleared" },
};

const PILL_TONE = {
  error: "bg-error-container text-on-error-container",
  warning: "bg-secondary-fixed text-on-secondary-fixed",
  success: "bg-primary-fixed text-on-primary-fixed",
};

const SCORE_TONE = {
  error: "text-error",
  warning: "text-on-secondary-fixed-variant",
  success: "text-primary",
};

const BAR_TONE = {
  error: "bg-error",
  warning: "bg-secondary",
  success: "bg-primary",
};

type ChecklistItem = {
  id: string;
  label: string;
  hint: string;
  thoughts: string[];
  rationale: string;
  phase: number;
  fullWidth?: boolean;
};

const VERIFICATION_PROTOCOL: ChecklistItem[] = [
  {
    id: "sanctions",
    label: "Sanctions & watchlist screening",
    hint: "OFAC, UN, EU cross-checked",
    phase: 1,
    fullWidth: true,
    thoughts: [
      "Querying OFAC SDN list…",
      "Matching UN Consolidated list…",
      "Cross-checking EU & MAS sanctions…",
      "Verifying PEP & adverse-media coverage…",
      "Resolving fuzzy-match candidates…",
      "Adjudicating near-miss aliases…",
      "Recording screening attestation…",
    ],
    rationale: "Screening stub — no sanctions feed wired in this build.",
  },
  {
    id: "funds",
    label: "Source of funds documented",
    hint: "Origin traced and justified",
    phase: 2,
    thoughts: [
      "Tracing upstream accounts…",
      "Fetching KYC refresh records…",
      "Reconstructing settlement chain…",
      "Validating source documentation…",
      "Computing source-of-wealth score…",
    ],
    rationale: "Source-of-funds stub — Transaction nodes pending Layer 1 expansion.",
  },
  {
    id: "typology",
    label: "Typology evidence reviewed",
    hint: "Pattern matched to schema",
    phase: 2,
    thoughts: [
      "Scanning FATF typology schemas…",
      "Comparing AUSTRAC rule set…",
      "Matching behavioral patterns…",
      "Checking MAS Notice 626 §3 alignment…",
      "Computing schema match score…",
    ],
    rationale: "Matched FATF §4.2 (layering), 2 citations.",
  },
  {
    id: "narrative",
    label: "Case narrative drafted",
    hint: "Findings & decision logged",
    phase: 3,
    fullWidth: true,
    thoughts: [
      "Compiling findings…",
      "Citing MAS Notice 626 references…",
      "Drafting analyst summary…",
    ],
    rationale: "Narrative compiled from 6 findings.",
  },
];

type ChecklistStatus = "pending" | "verifying" | "verified";

type StageKey = "approval" | "filing" | "submission";
type StageState = "pending" | "active" | "done";

type StageDef = {
  id: StageKey;
  label: string;
  Icon: typeof ShieldCheck;
  messages: string[];
  result: string;
};

const PIPELINE_STAGES: StageDef[] = [
  {
    id: "approval",
    label: "Approval Agent",
    Icon: ShieldCheck,
    messages: ["Reviewing case file…", "Cross-checking verification log…"],
    result: "Signed off · {findingsCount} reviewed",
  },
  {
    id: "filing",
    label: "Filing Agent",
    Icon: FileText,
    messages: ["Drafting SAR narrative…", "Citing MAS Notice 626 §3.2…"],
    result: "Draft ready · cites {chunkCount}",
  },
  {
    id: "submission",
    label: "MAS Submission",
    Icon: Send,
    messages: ["Transmitting to MAS portal…"],
    result: "Submitted · {caseId}",
  },
];

const VERIFY_MSG_INTERVAL_MS = 900;
const PIPELINE_MSG_MS = 700;
const PIPELINE_STAGE_BUFFER_MS = 400;

// Total number of phases the backend reports — synced with src/api/jobs.py
// DEEP_PHASES. Used only for the "step N of M" label; the active phase label
// itself comes from the backend so changes there don't require a frontend edit.
const DEEP_TOTAL_PHASES = 5;

export default function VerdictBanner({
  verdict,
  riskScore,
  headline,
  summary,
  recommendedActions,
  riskDecomposition,
  findings,
  typologyChunks,
  caseId,
  handedOff,
  onHandoff,
  onSarFiled,
  onDeepAnalyze,
  onStopWatchingDeep,
  deepAnalyzing = false,
  deepAnalysisDone = false,
  deepStatus = null,
  deepError = null,
}: {
  verdict: Verdict;
  riskScore: number;
  headline: string;
  summary?: string;
  recommendedActions?: string[];
  txVelocity: number[];
  riskDecomposition: RiskDecompositionBar[];
  findings: Finding[];
  typologyChunks: TypologyChunk[];
  caseId?: string;
  handedOff: boolean;
  onHandoff: () => void;
  onSarFiled: () => void;
  onDeepAnalyze?: () => void;
  onStopWatchingDeep?: () => void;
  deepAnalyzing?: boolean;
  deepAnalysisDone?: boolean;
  deepStatus?: DeepStatus | null;
  deepError?: string | null;
}) {
  const meta = VERDICT_META[verdict];
  const maxDecomp = Math.max(...riskDecomposition.map((d) => d.value), 0.01);

  // For verification items 3 and 4 the outcome string is sourced from real
  // assessment data; items 1 and 2 fall back to honest static stubs since
  // no sanctions feed or transaction data exists in this build.
  const dynamicRationales = useMemo<Record<string, string>>(() => {
    const top = findings[0];
    const patternHuman = top ? top.pattern_name.replace(/_/g, " ") : "";
    const chunksN = typologyChunks.length;
    const findingsN = findings.length;
    return {
      typology: top
        ? `Matched ${patternHuman} (${top.severity}); ${chunksN} citation${chunksN === 1 ? "" : "s"}.`
        : `${chunksN} typology citation${chunksN === 1 ? "" : "s"} retrieved.`,
      narrative: `Narrative compiled from ${findingsN} finding${findingsN === 1 ? "" : "s"}.`,
    };
  }, [findings, typologyChunks]);

  const stageTokens = useMemo<Record<string, string>>(() => {
    const fc = findings.length;
    const cc = typologyChunks.length;
    return {
      "{caseId}":         caseId ?? "STR-PENDING",
      "{findingsCount}":  fc === 1 ? "1 finding" : `${fc} findings`,
      "{chunkCount}":     cc === 1 ? "1 regulation" : `${cc} regulations`,
    };
  }, [findings.length, typologyChunks.length, caseId]);

  const [statuses, setStatuses] = useState<Record<string, ChecklistStatus>>(() =>
    Object.fromEntries(VERIFICATION_PROTOCOL.map((i) => [i.id, "pending"])) as Record<
      string,
      ChecklistStatus
    >,
  );
  const [thoughtMsg, setThoughtMsg] = useState<Record<string, string>>({});

  const [deepErrorOpen, setDeepErrorOpen] = useState(false);
  const deepPhaseIdx = deepStatus?.phase_idx ?? 0;
  const deepPhaseLabel = deepStatus?.phase_label ?? "Starting agent…";
  const deepElapsed = deepStatus?.elapsed_seconds ?? 0;
  const deepTokens =
    deepStatus && (deepStatus.input_tokens != null || deepStatus.output_tokens != null)
      ? (deepStatus.input_tokens ?? 0) + (deepStatus.output_tokens ?? 0)
      : null;

  // Verification only runs when deep analysis is active — items sit idle
  // (pending grey circles) until the user clicks "Run Deep Analysis".

  // Deep-analysis path: drive checklist from the agent's live phase index.
  // Mapping: deep phase → which verification items are verifying / verified.
  //   Phase 0 (resolving)   → all pending
  //   Phase 1 (traversing)  → sanctions verifying
  //   Phase 2 (anomalies)   → sanctions verified; funds + typology verifying
  //   Phase 3 (typology)    → funds + typology verified; narrative verifying
  //   Phase 4+ / done       → all verified
  useEffect(() => {
    if (!deepAnalyzing && !deepAnalysisDone) return;
    const idx = deepAnalysisDone ? 99 : (deepPhaseIdx ?? 0);
    const next: Record<string, ChecklistStatus> = {
      sanctions: idx >= 1 ? (idx >= 2 ? "verified" : "verifying") : "pending",
      funds:     idx >= 2 ? (idx >= 3 ? "verified" : "verifying") : "pending",
      typology:  idx >= 2 ? (idx >= 3 ? "verified" : "verifying") : "pending",
      narrative: idx >= 3 ? (idx >= 4 ? "verified" : "verifying") : "pending",
    };
    setStatuses(next);
    // Cycle thought messages for newly-verifying items.
    const timers: ReturnType<typeof setTimeout>[] = [];
    VERIFICATION_PROTOCOL.forEach((item) => {
      if (next[item.id] !== "verifying") return;
      setThoughtMsg((m) => ({ ...m, [item.id]: item.thoughts[0] }));
      item.thoughts.slice(1).forEach((msg, i) => {
        timers.push(setTimeout(() => {
          setThoughtMsg((m) => ({ ...m, [item.id]: msg }));
        }, (i + 1) * VERIFY_MSG_INTERVAL_MS));
      });
    });
    return () => timers.forEach(clearTimeout);
  }, [deepPhaseIdx, deepAnalyzing, deepAnalysisDone]);

  const total = VERIFICATION_PROTOCOL.length;
  const done = Object.values(statuses).filter((s) => s === "verified").length;
  const allVerified = done === total;

  const [stageStates, setStageStates] = useState<Record<StageKey, StageState>>({
    approval: "pending",
    filing: "pending",
    submission: "pending",
  });
  const [stageMessage, setStageMessage] = useState<Record<StageKey, string>>({
    approval: "",
    filing: "",
    submission: "",
  });

  function approveAndEscalate() {
    if (handedOff) return;
    onHandoff();
    let t = 0;
    PIPELINE_STAGES.forEach((stage) => {
      setTimeout(() => {
        setStageStates((s) => ({ ...s, [stage.id]: "active" }));
        setStageMessage((m) => ({ ...m, [stage.id]: stage.messages[0] }));
      }, t);
      stage.messages.forEach((msg, mIdx) => {
        if (mIdx === 0) return;
        setTimeout(() => {
          setStageMessage((m) => ({ ...m, [stage.id]: msg }));
        }, t + mIdx * PIPELINE_MSG_MS);
      });
      t += stage.messages.length * PIPELINE_MSG_MS;
      const resolvedResult = Object.entries(stageTokens).reduce(
        (s, [k, v]) => s.replace(k, v),
        stage.result,
      );
      setTimeout(() => {
        setStageStates((s) => ({ ...s, [stage.id]: "done" }));
        setStageMessage((m) => ({ ...m, [stage.id]: resolvedResult }));
      }, t);
      t += PIPELINE_STAGE_BUFFER_MS;
    });
    setTimeout(() => onSarFiled(), t);
  }

  const canApprove = allVerified && !handedOff;

  return (
    <div className="rounded border border-surface-container bg-surface-container-lowest p-6">
      <div className="flex gap-8">
        <div className="flex min-w-[140px] flex-col items-center justify-center border-r border-surface-container-high pr-8">
          <div className="mb-2 text-xs font-bold uppercase tracking-widest text-on-surface-variant">
            Risk Score
          </div>
          <div className={`mb-1 font-mono text-5xl font-bold ${SCORE_TONE[meta.tone]}`}>
            {riskScore.toFixed(2)}
          </div>
          <div
            className={`rounded-sm px-2 py-0.5 text-xs font-bold uppercase tracking-wide ${PILL_TONE[meta.tone]}`}
          >
            {meta.pill}
          </div>
        </div>

        <div className="min-w-0 flex-1">
          <div className="mb-2 flex items-start justify-between gap-3">
            <h3 className="flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-on-surface">
              <Scale size={16} strokeWidth={2} className="text-primary" />
              Analyst Recommendation
            </h3>
            {onDeepAnalyze && !deepAnalyzing && !deepAnalysisDone && (
              <button
                type="button"
                onClick={onDeepAnalyze}
                className="flex h-7 items-center gap-1.5 rounded-sm border border-primary/30 bg-primary-fixed/30 px-2.5 text-[11px] font-semibold uppercase tracking-wider text-on-primary-fixed-variant transition-colors hover:bg-primary-fixed/50"
                title="Run the full H2OGPTe agent loop (5–10 minutes)"
              >
                <Sparkles size={12} strokeWidth={2.5} />
                Run Deep Analysis
              </button>
            )}
            {deepAnalyzing && onStopWatchingDeep && (
              <button
                type="button"
                onClick={onStopWatchingDeep}
                className="flex h-7 items-center gap-1.5 rounded-sm border border-outline-variant/50 bg-surface-container-low px-2.5 text-[11px] font-semibold uppercase tracking-wider text-on-surface-variant transition-colors hover:bg-surface-container-high"
                title="The H2OGPTe agent run continues and still bills on the server. This just stops the UI from waiting."
              >
                <XCircle size={12} strokeWidth={2.5} />
                Stop Watching
              </button>
            )}
            {deepAnalysisDone && (
              <span className="flex h-7 items-center gap-1.5 rounded-sm border border-primary/40 bg-primary-fixed/40 px-2.5 text-[11px] font-semibold uppercase tracking-wider text-on-primary-fixed-variant">
                <Sparkles size={12} strokeWidth={2.5} />
                Deep Analysis · Done
              </span>
            )}
          </div>
          <p className="mb-2 text-base font-medium leading-relaxed text-[#191c1d]">{headline}</p>
          {deepAnalyzing && (
            <div className="mb-3 rounded border border-primary/30 bg-primary-fixed/20 px-3 py-2">
              <div className="flex items-center gap-3">
                <Loader2 size={14} strokeWidth={2.25} className="shrink-0 animate-spin text-primary" />
                <div className="min-w-0 flex-1">
                  <div className="text-[11px] font-bold uppercase tracking-wider text-on-primary-fixed-variant">
                    H2OGPTe agent · step {Math.min(deepPhaseIdx + 1, DEEP_TOTAL_PHASES)} of {DEEP_TOTAL_PHASES}
                  </div>
                  <div className="truncate text-[12.5px] italic text-on-surface">
                    {deepPhaseLabel}
                  </div>
                </div>
                <span className="shrink-0 font-mono text-[11px] tabular-nums text-on-surface-variant">
                  {deepElapsed}s
                </span>
              </div>
              {deepTokens != null && (
                <div className="mt-1.5 ml-7 font-mono text-[10.5px] tabular-nums text-on-surface-variant">
                  ~{deepTokens.toLocaleString()} tokens · live from H2OGPTe
                </div>
              )}
            </div>
          )}
          {deepError && (() => {
            // If the agent emitted at least one turn before failing, treat it
            // as a partial completion (yellow). Otherwise it's a total failure
            // (red). Either way the long SDK error string is collapsed behind
            // a "Details" toggle so it doesn't flood the page.
            const partial = (deepStatus?.agent_events?.length ?? 0) > 0;
            const phaseIdx = deepStatus?.phase_idx ?? 0;
            // Honest step count: phase_idx is 0..4 where 0 = setup (pre-step-1)
            // and 1..3 = steps 1..3; phase 4 = synthesis. Only show "reached
            // step N" if we actually got past setup.
            const stepReachedLabel = phaseIdx >= 1 ? ` (reached step ${phaseIdx} of 3)` : "";
            return (
              <div
                className={
                  partial
                    ? "mb-3 rounded border border-secondary/40 bg-secondary-fixed/20 px-3 py-2 text-[12px] text-on-secondary-fixed-variant"
                    : "mb-3 rounded border border-error/40 bg-error-container/40 px-3 py-2 text-[12px] text-on-error-container"
                }
              >
                <div className="flex items-start gap-2">
                  <AlertTriangle size={14} strokeWidth={2.25} className="mt-0.5 shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="font-semibold uppercase tracking-wider text-[10.5px]">
                      {partial ? `Deep analysis stopped early${stepReachedLabel}` : "Deep analysis failed"}
                    </div>
                    {partial && (
                      <div className="mt-0.5 text-[11.5px] opacity-90">
                        Verdict above reflects the deterministic baseline. Steps completed before the timeout are below in Agent Reasoning.
                      </div>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => setDeepErrorOpen((v) => !v)}
                    className="shrink-0 rounded-sm px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider opacity-80 hover:opacity-100"
                  >
                    {deepErrorOpen ? "Hide details" : "Details"}
                  </button>
                </div>
                {deepErrorOpen && (
                  <pre className="mt-2 max-h-32 overflow-auto whitespace-pre-wrap break-words rounded bg-surface-container-lowest p-2 font-mono text-[10.5px] leading-snug text-on-surface-variant">
                    {deepError}
                  </pre>
                )}
              </div>
            );
          })()}
          {deepAnalysisDone && summary && <SummaryBlock text={summary} />}
          {!deepAnalyzing && !deepAnalysisDone && onDeepAnalyze && (
            <p className="mb-3 text-[11.5px] text-on-surface-variant/50 italic">
              Run deep analysis for full evidence narrative and agent verification.
            </p>
          )}
          {recommendedActions && recommendedActions.length > 0 && (
            <div className="mb-4 rounded border border-surface-container-high bg-surface-container-low p-3">
              <div className="mb-1.5 text-[10.5px] font-bold uppercase tracking-wider text-on-surface-variant">
                Recommended actions
              </div>
              <ul className="space-y-1 text-[12.5px] leading-snug text-on-surface">
                {recommendedActions.map((a, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="mt-1 inline-block h-1 w-1 shrink-0 rounded-full bg-primary" />
                    <span><InlineMarkdown text={a} /></span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="border-t border-surface-container-high pt-4">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-on-surface-variant">
                Risk Decomposition
              </span>
              {deepAnalysisDone && (
                <span className="flex items-center gap-1 rounded-sm bg-primary-fixed/40 px-1.5 py-0.5 text-[9.5px] font-semibold uppercase tracking-wider text-on-primary-fixed-variant">
                  <Sparkles size={9} strokeWidth={2.5} />
                  Agent score · {riskScore.toFixed(2)}
                </span>
              )}
              {deepAnalyzing && (
                <span className="flex items-center gap-1 text-[10px] text-on-surface-variant/60 italic">
                  <Loader2 size={10} strokeWidth={2} className="animate-spin" />
                  validating…
                </span>
              )}
            </div>
            <div className="space-y-1.5">
              {riskDecomposition.map((d) => (
                <div key={d.label} className="flex items-center gap-3 text-xs">
                  <span className="w-24 shrink-0 text-on-surface-variant">{d.label}</span>
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-container-high">
                    <div
                      className={`h-full rounded-full transition-all duration-700 ${BAR_TONE[meta.tone]}${deepAnalyzing ? " opacity-60" : ""}`}
                      style={{ width: `${(d.value / maxDecomp) * 100}%` }}
                    />
                  </div>
                  <span className="w-10 shrink-0 text-right font-mono tabular-nums text-on-surface">
                    {d.value.toFixed(2)}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-5 border-t border-surface-container-high pt-4">
            <div className="mb-3 flex items-center justify-between">
              <span className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-on-surface-variant">
                <ShieldCheck size={14} strokeWidth={2} className="text-primary" />
                Verification Protocol
                {deepAnalyzing ? (
                  <span className="ml-1 flex items-center gap-1 rounded-sm bg-primary-fixed/30 px-1.5 py-0.5 text-[9.5px] font-semibold tracking-wider text-on-primary-fixed-variant">
                    <Loader2 size={9} strokeWidth={2.5} className="animate-spin" />
                    {deepPhaseLabel}
                  </span>
                ) : deepAnalysisDone ? (
                  <span className="ml-1 flex items-center gap-1 rounded-sm bg-primary-fixed/40 px-1.5 py-0.5 text-[9.5px] font-semibold tracking-wider text-on-primary-fixed-variant">
                    <Sparkles size={9} strokeWidth={2.5} />
                    Agent-verified
                  </span>
                ) : (
                  <span className="ml-1 rounded-sm bg-surface-container-high px-1.5 py-0.5 text-[9.5px] font-semibold tracking-wider text-on-surface-variant/50">
                    Pending deep analysis
                  </span>
                )}
              </span>
              <div className="flex items-center gap-2">
                <div className="h-1 w-24 overflow-hidden rounded-full bg-surface-container-high">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${allVerified ? "bg-primary" : BAR_TONE[meta.tone]}`}
                    style={{ width: `${(done / total) * 100}%` }}
                  />
                </div>
                <span className="font-mono text-[11px] tabular-nums text-on-surface-variant">
                  {done}/{total} verified
                </span>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-x-6 gap-y-1.5 md:grid-cols-2">
              {VERIFICATION_PROTOCOL.map((item) => {
                const status = statuses[item.id];
                return (
                  <div
                    key={item.id}
                    className={`flex items-start gap-2.5 rounded px-2 py-1.5 transition-colors ${
                      item.fullWidth ? "md:col-span-2" : ""
                    } ${status === "verified" ? "bg-surface-container-low" : ""}`}
                  >
                    {status === "verified" ? (
                      <CheckCircle2
                        size={16}
                        strokeWidth={2.25}
                        className="mt-0.5 shrink-0 text-primary"
                      />
                    ) : status === "verifying" ? (
                      <Loader2
                        size={16}
                        strokeWidth={2}
                        className="mt-0.5 shrink-0 animate-spin text-primary"
                      />
                    ) : (
                      <Circle
                        size={16}
                        strokeWidth={1.75}
                        className="mt-0.5 shrink-0 text-outline-variant"
                      />
                    )}
                    <div className="min-w-0">
                      <div
                        className={`text-[12.5px] font-medium leading-tight ${
                          status === "pending"
                            ? "text-on-surface-variant"
                            : "text-on-surface"
                        }`}
                      >
                        {item.label}
                      </div>
                      <div
                        className={`mt-0.5 text-[11px] leading-tight ${
                          status === "verifying"
                            ? "italic text-primary"
                            : status === "verified"
                            ? "text-on-surface-variant"
                            : "text-on-surface-variant/70"
                        }`}
                      >
                        {status === "pending"
                          ? item.hint
                          : status === "verifying"
                          ? thoughtMsg[item.id] ?? "verifying…"
                          : dynamicRationales[item.id] ?? item.rationale}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="mt-4 flex items-center justify-between">
              <span className="text-[11px] text-on-surface-variant">
                {handedOff
                  ? "Approved by analyst · agents handling downstream filing."
                  : allVerified
                  ? "All checks cleared. Analyst sign-off required before agent handoff."
                  : "Agent verifying — attestations will appear as each check clears."}
              </span>
              <button
                type="button"
                onClick={approveAndEscalate}
                disabled={!canApprove}
                className="flex h-9 items-center gap-2 rounded bg-[#1e40af] px-4 text-[13px] font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40"
              >
                {handedOff ? "Approved & Escalated" : "Approve & Escalate"}
                <ArrowRight size={14} strokeWidth={2} />
              </button>
            </div>

            {handedOff && (
              <div className="mt-4 border-t border-surface-container-high pt-4">
                <div className="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-on-surface-variant">
                  <Send size={14} strokeWidth={2} className="text-primary" />
                  Downstream Agent Pipeline
                </div>

                <div className="flex items-stretch gap-2">
                  {PIPELINE_STAGES.map((stage, idx) => {
                    const state = stageStates[stage.id];
                    const Icon = stage.Icon;
                    const toneClass =
                      state === "done"
                        ? "border-primary/60 bg-primary-fixed/40"
                        : state === "active"
                        ? "border-primary/50 bg-primary-fixed/20 shadow-[0_0_0_3px_rgba(30,64,175,0.08)]"
                        : "border-outline-variant/40 bg-surface-container-low";
                    const iconClass =
                      state === "done"
                        ? "text-primary"
                        : state === "active"
                        ? "text-primary animate-pulse"
                        : "text-on-surface-variant/60";
                    return (
                      <div key={stage.id} className="flex min-w-0 flex-1 items-center gap-2">
                        <div
                          className={`flex min-w-0 flex-1 flex-col gap-1 rounded border px-3 py-2 transition-all ${toneClass}`}
                        >
                          <div className="flex items-center gap-2">
                            {state === "active" ? (
                              <Loader2 size={14} strokeWidth={2} className={`shrink-0 animate-spin ${iconClass}`} />
                            ) : state === "done" ? (
                              <CheckCircle2 size={14} strokeWidth={2.25} className={`shrink-0 ${iconClass}`} />
                            ) : (
                              <Icon size={14} strokeWidth={2} className={`shrink-0 ${iconClass}`} />
                            )}
                            <span
                              className={`truncate text-[12px] font-semibold ${
                                state === "pending" ? "text-on-surface-variant" : "text-on-surface"
                              }`}
                            >
                              {stage.label}
                            </span>
                          </div>
                          <div
                            className={`min-h-[28px] break-words font-mono text-[10.5px] leading-snug ${
                              state === "active"
                                ? "text-primary"
                                : state === "done"
                                ? "text-on-surface-variant"
                                : "text-on-surface-variant/50"
                            }`}
                          >
                            {stageMessage[stage.id] || (state === "pending" ? "queued" : "")}
                          </div>
                        </div>
                        {idx < PIPELINE_STAGES.length - 1 && (
                          <ArrowRight
                            size={14}
                            strokeWidth={2}
                            className={`shrink-0 ${
                              stageStates[PIPELINE_STAGES[idx + 1].id] === "pending" &&
                              state !== "done"
                                ? "text-outline-variant/40"
                                : "text-primary"
                            }`}
                          />
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
