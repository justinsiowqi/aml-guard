import type { CaseAssessment } from "@/lib/types";
import { Building2, MapPin, Briefcase } from "lucide-react";

export default function EntityHeader({
  subject,
  caseId,
}: {
  subject: CaseAssessment["subject"];
  caseId: string;
}) {
  return (
    <div>
      <div className="mb-2 flex items-center gap-2 text-[11px] uppercase tracking-[0.16em] text-text-muted">
        <span>Subject</span>
        <span>·</span>
        <span>{caseId}</span>
      </div>
      <h2 className="font-display text-4xl leading-tight text-text sm:text-5xl">
        {subject.name}
      </h2>
      <div className="mt-3 flex flex-wrap items-center gap-2 text-[12px]">
        <Chip icon={Building2} label={subject.type} />
        <Chip icon={MapPin} label={subject.jurisdiction} tone="danger" />
        <Chip icon={Briefcase} label="Mossack Fonseca (historic)" tone="warning" />
        <span className="text-text-muted">·</span>
        <span className="text-text-muted">{subject.profile_snippet}</span>
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
