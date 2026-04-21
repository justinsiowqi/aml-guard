import type { CaseAssessment } from "@/lib/types";
import { Building2, MapPin, Briefcase, FileText } from "lucide-react";

export default function EntityHeader({
  subject,
  caseId,
}: {
  subject: CaseAssessment["subject"];
  caseId: string;
}) {
  return (
    <div>
      <div className="flex items-start justify-between gap-4">
        <h2 className="font-display text-4xl leading-tight text-text sm:text-5xl">
          {subject.name}
        </h2>
        <code className="mt-2 shrink-0 rounded-sm bg-surface-alt px-2 py-1 font-mono text-[11px] text-text-muted">
          {caseId}
        </code>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2 text-[12px]">
        <Chip icon={Building2} label={subject.type} />
        <Chip icon={MapPin} label={subject.jurisdiction} tone="danger" />
        <Chip icon={Briefcase} label="Mossack Fonseca (historic)" tone="warning" />
      </div>
      <div className="mt-4 flex max-w-[72ch] items-start gap-2.5 rounded-md border border-border/70 bg-surface-alt/60 px-3.5 py-2.5">
        <FileText size={13} strokeWidth={1.75} className="mt-[3px] shrink-0 text-text-muted" />
        <p className="text-pretty text-[13px] leading-relaxed text-text/80">
          {subject.profile_snippet}
        </p>
      </div>
    </div>
  );
}

function Chip({
  icon: Icon,
  label,
  tone = "neutral",
}: {
  icon: typeof Building2;
  label: string;
  tone?: "neutral" | "danger" | "warning";
}) {
  const tones = {
    neutral: "border-border bg-surface text-text",
    danger: "border-danger/20 bg-danger/5 text-danger",
    warning: "border-warning/20 bg-warning/5 text-warning",
  };
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 ${tones[tone]}`}>
      <Icon size={12} strokeWidth={1.75} />
      {label}
    </span>
  );
}
