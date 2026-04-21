"use client";

import { useState } from "react";
import type { Verdict } from "@/lib/types";
import { ArrowRight, CheckCircle2, Circle, Scale, ShieldCheck } from "lucide-react";
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

const RISK_DECOMPOSITION = [
  { label: "Jurisdiction",  value: 0.28 },
  { label: "Structuring",   value: 0.31 },
  { label: "Intermediary",  value: 0.15 },
  { label: "Velocity",      value: 0.10 },
];

type ChecklistItem = { id: string; label: string; hint: string };

const VERIFICATION_PROTOCOL: ChecklistItem[] = [
  { id: "sanctions",   label: "Sanctions & watchlist screening", hint: "OFAC, UN, EU cross-checked" },
  { id: "funds",       label: "Source of funds documented",      hint: "Origin traced and justified" },
  { id: "ownership",   label: "Beneficial ownership confirmed",  hint: "UBO chain ≤ 25% verified" },
  { id: "typology",    label: "Typology evidence reviewed",      hint: "Pattern matched to schema" },
  { id: "jurisdiction",label: "Counterparty jurisdiction risk",  hint: "Corridor risk acknowledged" },
  { id: "narrative",   label: "Case narrative drafted",          hint: "Findings & decision logged" },
];

export default function VerdictBanner({
  verdict,
  riskScore,
  headline,
  txVelocity,
}: {
  verdict: Verdict;
  riskScore: number;
  headline: string;
  txVelocity: number[];
}) {
  const meta = VERDICT_META[verdict];
  const maxTx = Math.max(...txVelocity, 1);
  const maxDecomp = Math.max(...RISK_DECOMPOSITION.map((d) => d.value));

  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [handedOff, setHandedOff] = useState(false);

  const total = VERIFICATION_PROTOCOL.length;
  const done = checked.size;
  const complete = done === total;

  const toggle = (id: string) => {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

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
                {RISK_DECOMPOSITION.map((d) => (
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
              </span>
              <div className="flex items-center gap-2">
                <div className="h-1 w-24 overflow-hidden rounded-full bg-surface-container-high">
                  <div
                    className={`h-full rounded-full transition-all ${complete ? "bg-primary" : BAR_TONE[meta.tone]}`}
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
                const isChecked = checked.has(item.id);
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => toggle(item.id)}
                    disabled={handedOff}
                    className={`group flex items-start gap-2.5 rounded px-2 py-1.5 text-left transition-colors hover:bg-surface-container-low disabled:cursor-not-allowed disabled:opacity-60 ${
                      isChecked ? "bg-surface-container-low" : ""
                    }`}
                  >
                    {isChecked ? (
                      <CheckCircle2
                        size={16}
                        strokeWidth={2.25}
                        className="mt-0.5 shrink-0 text-primary"
                      />
                    ) : (
                      <Circle
                        size={16}
                        strokeWidth={1.75}
                        className="mt-0.5 shrink-0 text-outline-variant group-hover:text-on-surface-variant"
                      />
                    )}
                    <div className="min-w-0">
                      <div
                        className={`text-[12.5px] font-medium leading-tight ${
                          isChecked
                            ? "text-on-surface-variant line-through decoration-on-surface-variant/40"
                            : "text-on-surface"
                        }`}
                      >
                        {item.label}
                      </div>
                      <div className="mt-0.5 text-[11px] leading-tight text-on-surface-variant/70">
                        {item.hint}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>

            <div className="mt-4 flex items-center justify-between">
              <span className="text-[11px] text-on-surface-variant">
                {handedOff
                  ? "Case relayed — awaiting Approval Agent sign-off."
                  : complete
                  ? "All checks verified. Ready for agent handoff."
                  : `Complete ${total - done} more ${total - done === 1 ? "check" : "checks"} to enable handoff.`}
              </span>
              <button
                type="button"
                onClick={() => setHandedOff(true)}
                disabled={!complete || handedOff}
                className="flex h-9 items-center gap-2 rounded bg-[#1e40af] px-4 text-[13px] font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40"
              >
                {handedOff ? "Relayed to Approval Agent" : "Relay to Approval Agent"}
                <ArrowRight size={14} strokeWidth={2} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
