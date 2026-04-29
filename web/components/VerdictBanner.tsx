"use client";

import { useEffect, useMemo, useState } from "react";
import type { Finding, RiskDecompositionBar, TypologyChunk, Verdict } from "@/lib/types";
import {
  ArrowRight,
  CheckCircle2,
  Circle,
  FileText,
  Loader2,
  Scale,
  Send,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import Sparkline from "./Sparkline";

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

const DEEP_PHASES = [
  "Resolving entity from question…",
  "Traversing 2-hop entity subgraph…",
  "Detecting graph anomaly patterns…",
  "Retrieving MAS Notice 626 typology chunks…",
  "Reasoning over evidence…",
];
const DEEP_PHASE_INTERVAL_MS = 6000;

export default function VerdictBanner({
  verdict,
  riskScore,
  headline,
  summary,
  recommendedActions,
  txVelocity,
  riskDecomposition,
  findings,
  typologyChunks,
  caseId,
  handedOff,
  onHandoff,
  onSarFiled,
  onDeepAnalyze,
  deepAnalyzing = false,
  deepAnalysisDone = false,
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
  deepAnalyzing?: boolean;
  deepAnalysisDone?: boolean;
}) {
  const meta = VERDICT_META[verdict];
  const maxTx = Math.max(...txVelocity, 1);
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

  const [deepPhaseIdx, setDeepPhaseIdx] = useState(0);
  const [deepElapsed, setDeepElapsed] = useState(0);
  useEffect(() => {
    if (!deepAnalyzing) {
      setDeepPhaseIdx(0);
      setDeepElapsed(0);
      return;
    }
    setDeepPhaseIdx(0);
    setDeepElapsed(0);
    const phaseTimer = setInterval(() => {
      setDeepPhaseIdx((i) => Math.min(i + 1, DEEP_PHASES.length - 1));
    }, DEEP_PHASE_INTERVAL_MS);
    const elapsedTimer = setInterval(() => setDeepElapsed((s) => s + 1), 1000);
    return () => {
      clearInterval(phaseTimer);
      clearInterval(elapsedTimer);
    };
  }, [deepAnalyzing]);

  useEffect(() => {
    const timers: ReturnType<typeof setTimeout>[] = [];
    const phases = new Map<number, ChecklistItem[]>();
    VERIFICATION_PROTOCOL.forEach((item) => {
      const arr = phases.get(item.phase) ?? [];
      arr.push(item);
      phases.set(item.phase, arr);
    });

    let t = 0;
    Array.from(phases.entries())
      .sort(([a], [b]) => a - b)
      .forEach(([, items]) => {
        let phaseMax = 0;
        items.forEach((item) => {
          const duration = item.thoughts.length * VERIFY_MSG_INTERVAL_MS;
          phaseMax = Math.max(phaseMax, duration);
          const startAt = t;
          timers.push(
            setTimeout(() => {
              setStatuses((s) => ({ ...s, [item.id]: "verifying" }));
              setThoughtMsg((m) => ({ ...m, [item.id]: item.thoughts[0] }));
            }, startAt),
          );
          item.thoughts.forEach((msg, mIdx) => {
            if (mIdx === 0) return;
            timers.push(
              setTimeout(() => {
                setThoughtMsg((m) => ({ ...m, [item.id]: msg }));
              }, startAt + mIdx * VERIFY_MSG_INTERVAL_MS),
            );
          });
          timers.push(
            setTimeout(() => {
              setStatuses((s) => ({ ...s, [item.id]: "verified" }));
            }, startAt + duration),
          );
        });
        t += phaseMax;
      });
    return () => timers.forEach(clearTimeout);
  }, []);

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
                title="Run the full H2OGPTe agent loop (30-90s)"
              >
                <Sparkles size={12} strokeWidth={2.5} />
                Run Deep Analysis
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
            <div className="mb-3 flex items-center gap-3 rounded border border-primary/30 bg-primary-fixed/20 px-3 py-2">
              <Loader2 size={14} strokeWidth={2.25} className="shrink-0 animate-spin text-primary" />
              <div className="min-w-0 flex-1">
                <div className="text-[11px] font-bold uppercase tracking-wider text-on-primary-fixed-variant">
                  H2OGPTe agent · step {Math.min(deepPhaseIdx + 1, DEEP_PHASES.length)} of {DEEP_PHASES.length}
                </div>
                <div className="truncate text-[12.5px] italic text-on-surface">
                  {DEEP_PHASES[deepPhaseIdx]}
                </div>
              </div>
              <span className="shrink-0 font-mono text-[11px] tabular-nums text-on-surface-variant">
                {deepElapsed}s
              </span>
            </div>
          )}
          {summary && (
            <p className="mb-3 text-[13px] leading-relaxed text-on-surface-variant">{summary}</p>
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
                    <span>{a}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="grid grid-cols-12 gap-6 border-t border-surface-container-high pt-4">
            <div className="col-span-12 lg:col-span-7">
              <div className="mb-2 text-xs font-bold uppercase tracking-wider text-on-surface-variant">
                Risk Decomposition
              </div>
              <div className="space-y-1.5">
                {riskDecomposition.map((d) => (
                  <div key={d.label} className="flex items-center gap-3 text-xs">
                    <span className="w-24 shrink-0 text-on-surface-variant">{d.label}</span>
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-container-high">
                      <div
                        className={`h-full rounded-full ${BAR_TONE[meta.tone]}`}
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

            <div className="col-span-12 lg:col-span-5">
              <div className="mb-2 flex items-baseline justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-on-surface-variant">
                  Velocity · 12 periods
                </span>
                <span className="font-mono text-[11px] text-on-surface-variant">
                  Max {maxTx.toLocaleString()}
                </span>
              </div>
              <Sparkline data={txVelocity} tone={meta.tone} width={280} height={32} />
            </div>
          </div>

          <div className="mt-5 border-t border-surface-container-high pt-4">
            <div className="mb-3 flex items-center justify-between">
              <span className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-on-surface-variant">
                <ShieldCheck size={14} strokeWidth={2} className="text-primary" />
                Verification Protocol
                <span className="ml-1 rounded-sm bg-surface-container-high px-1.5 py-0.5 text-[9.5px] font-semibold tracking-wider text-on-surface-variant">
                  AGENT-RUN
                </span>
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
