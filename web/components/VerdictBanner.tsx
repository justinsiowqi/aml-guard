import type { Verdict } from "@/lib/types";
import { Scale } from "lucide-react";
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

  return (
    <div className="h-full rounded border border-surface-container bg-surface-container-lowest p-6">
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

        <div className="flex-1">
          <h3 className="mb-2 flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-on-surface">
            <Scale size={16} strokeWidth={2} className="text-primary" />
            Analyst Recommendation
          </h3>
          <p className="mb-4 text-base font-medium leading-relaxed text-on-surface">{headline}</p>

          <div className="border-t border-surface-container-high pt-4">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-on-surface-variant">
                Transaction Velocity · last 12 periods
              </span>
              <span className="font-mono text-xs text-on-surface-variant">
                Max: {maxTx.toLocaleString()}
              </span>
            </div>
            <Sparkline data={txVelocity} tone={meta.tone} width={480} height={32} />
            <div className="mt-2 text-[11px] italic text-on-surface-variant">
              Recommendation — <span className="not-italic text-on-surface">{meta.note}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
