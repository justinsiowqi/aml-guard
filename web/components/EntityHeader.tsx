import type { CaseAssessment } from "@/lib/types";
import { CheckCircle2, FileDown, Loader2 } from "lucide-react";

type Phase = "idle" | "streaming" | "settled";

const STATUS_LABEL: Record<Phase, string> = {
  idle: "Pending",
  streaming: "Streaming",
  settled: "Settled",
};

export default function EntityHeader({
  subject,
  caseId,
  phase = "settled",
  handedOff = false,
  sarFiled = false,
}: {
  subject: CaseAssessment["subject"];
  caseId?: string;
  phase?: Phase;
  handedOff?: boolean;
  sarFiled?: boolean;
}) {
  return (
    <div className="mb-8">
      <div className="flex items-center justify-between gap-6">
        <div className="flex min-w-0 items-center gap-3">
          <h1 className="text-3xl font-black tracking-tight text-on-surface">{subject.name}</h1>
          <span className="rounded-sm bg-[#444653] px-2 py-0.5 text-xs font-bold uppercase tracking-wider text-white">
            {STATUS_LABEL[phase]}
          </span>
        </div>

        <div className="flex shrink-0 items-center gap-3">
          <button
            type="button"
            className="flex items-center gap-2 rounded border border-outline-variant/30 px-4 py-2 text-sm font-semibold text-on-surface transition-colors hover:bg-surface-container-low"
          >
            <FileDown size={16} strokeWidth={1.75} />
            Export PDF
          </button>
          {sarFiled ? (
            <div className="flex items-center gap-2 rounded border border-primary/40 bg-primary-container px-4 py-2 text-sm font-semibold text-on-primary-container shadow-sm">
              <CheckCircle2 size={16} strokeWidth={2} />
              <span>SAR filed · MAS-STR-2026-0417</span>
            </div>
          ) : handedOff ? (
            <div className="flex items-center gap-2 rounded border border-primary/30 bg-primary-fixed/30 px-4 py-2 text-sm font-semibold text-on-surface shadow-sm">
              <Loader2 size={16} strokeWidth={2} className="animate-spin text-primary" />
              <span>Agents filing SAR…</span>
            </div>
          ) : null}
        </div>
      </div>

      <div className="mt-2 grid grid-cols-12 gap-6">
        <div className="col-span-12 text-sm text-on-surface-variant lg:col-span-8">
          {subject.profile_snippet}
        </div>
      </div>
    </div>
  );
}
