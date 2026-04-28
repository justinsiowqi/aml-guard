"use client";

import { useEffect, useState } from "react";
import type { RiskDecompositionBar, Verdict } from "@/lib/types";
import {
  ArrowRight,
  CheckCircle2,
  Circle,
  FileText,
  Loader2,
  Scale,
  Send,
  ShieldCheck,
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
    rationale: "Screened OFAC, UN, EU, MAS — no hits.",
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
    rationale: "Traced 3 upstream accounts; 2 flagged for docs.",
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
    result: "Signed off · attestations valid",
  },
  {
    id: "filing",
    label: "Filing Agent",
    Icon: FileText,
    messages: ["Drafting SAR narrative…", "Citing MAS Notice 626 §3.2…"],
    result: "Draft ready · 342 words",
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

export default function VerdictBanner({
  verdict,
  riskScore,
  headline,
  txVelocity,
  riskDecomposition,
  caseId,
  handedOff,
  onHandoff,
  onSarFiled,
}: {
  verdict: Verdict;
  riskScore: number;
  headline: string;
  txVelocity: number[];
  riskDecomposition: RiskDecompositionBar[];
  caseId?: string;
  handedOff: boolean;
  onHandoff: () => void;
  onSarFiled: () => void;
}) {
  const meta = VERDICT_META[verdict];
  const maxTx = Math.max(...txVelocity, 1);
  const maxDecomp = Math.max(...riskDecomposition.map((d) => d.value), 0.01);

  const [statuses, setStatuses] = useState<Record<string, ChecklistStatus>>(() =>
    Object.fromEntries(VERIFICATION_PROTOCOL.map((i) => [i.id, "pending"])) as Record<
      string,
      ChecklistStatus
    >,
  );
  const [thoughtMsg, setThoughtMsg] = useState<Record<string, string>>({});

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
      const resolvedResult = stage.result.replace("{caseId}", caseId ?? "STR-PENDING");
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
          <h3 className="mb-2 flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-on-surface">
            <Scale size={16} strokeWidth={2} className="text-primary" />
            Analyst Recommendation
          </h3>
          <p className="mb-4 text-base font-medium leading-relaxed text-[#191c1d]">{headline}</p>

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
                          : item.rationale}
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
