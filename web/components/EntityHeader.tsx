import type { CaseAssessment } from "@/lib/types";
import { FileDown, Gavel } from "lucide-react";

type Phase = "idle" | "streaming" | "settled";

const STATUS_LABEL: Record<Phase, string> = {
  idle: "Pending",
  streaming: "Streaming",
  settled: "Settled",
};

export default function EntityHeader({
  subject,
  phase = "settled",
}: {
  subject: CaseAssessment["subject"];
  caseId?: string;
  phase?: Phase;
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

        <div className="flex shrink-0 gap-3">
          <button
            type="button"
            className="flex items-center gap-2 rounded border border-outline-variant/30 px-4 py-2 text-sm font-semibold text-on-surface transition-colors hover:bg-surface-container-low"
          >
            <FileDown size={16} strokeWidth={1.75} />
            Export PDF
          </button>
          <button
            type="button"
            className="flex items-center gap-2 rounded bg-[#1e40af] px-4 py-2 text-sm font-semibold text-white shadow-sm transition-opacity hover:opacity-90"
          >
            <Gavel size={16} strokeWidth={1.75} />
            File SAR
          </button>
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
