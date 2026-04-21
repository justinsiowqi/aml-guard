import type { Verdict } from "@/lib/types";
import RiskGauge from "./RiskGauge";
import Sparkline from "./Sparkline";

const VERDICT_META: Record<
  Verdict,
  { label: string; tone: "danger" | "warning" | "success"; note: string }
> = {
  HIGH_RISK:   { label: "HIGH_RISK",   tone: "danger",  note: "File STR; freeze eligibility review" },
  MEDIUM_RISK: { label: "MEDIUM_RISK", tone: "warning", note: "Escalate to senior investigator"    },
  LOW_RISK:    { label: "LOW_RISK",    tone: "success", note: "Continue periodic monitoring"       },
  CLEARED:     { label: "CLEARED",     tone: "success", note: "No further action"                  },
};

const TONE_BG = {
  danger: "bg-danger/5 border-danger",
  warning: "bg-warning/5 border-warning",
  success: "bg-success/5 border-success",
};

const TONE_TEXT = {
  danger: "text-danger",
  warning: "text-warning",
  success: "text-success",
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
  return (
    <div className={`rounded-md border border-l-4 bg-surface px-6 py-6 shadow-sm ${TONE_BG[meta.tone]}`}>
      <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
        <div className="min-w-0 flex-1">
          <div className="mb-1 text-[11px] uppercase tracking-[0.18em] text-text-muted">
            Verdict
          </div>
          <div className={`font-display text-[44px] leading-none tracking-tight sm:text-[56px] ${TONE_TEXT[meta.tone]}`}>
            {meta.label}
          </div>
          <p className="mt-3 max-w-xl text-sm text-text/90">{headline}</p>
          <p className="mt-1 text-[12px] text-text-muted">
            Recommendation — <span className="text-text">{meta.note}</span>
          </p>
        </div>
        <div className="flex shrink-0 items-start gap-8">
          <RiskGauge value={riskScore} tone={meta.tone} />
        </div>
      </div>

      <div className="mt-6 flex flex-wrap items-end gap-6 border-t border-border/70 pt-4">
        <div>
          <div className="text-[11px] uppercase tracking-[0.14em] text-text-muted">
            Transaction velocity · last 12 periods
          </div>
          <div className="mt-2">
            <Sparkline data={txVelocity} tone={meta.tone} />
          </div>
        </div>
        <div className="tabular text-[12px] text-text-muted">
          4 inbound wires · 22 days · each &lt; SGD 500,000
        </div>
      </div>
    </div>
  );
}
