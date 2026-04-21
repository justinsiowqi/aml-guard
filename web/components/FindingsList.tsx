import type { Finding, Severity } from "@/lib/types";

const SEV_ORDER: Record<Severity, number> = { HIGH: 0, MEDIUM: 1, LOW: 2, INFO: 3 };

const SEV_TONE: Record<Severity, { border: string; label: string; chipBg: string; chipText: string }> = {
  HIGH:   { border: "border-l-danger",   label: "HIGH",   chipBg: "bg-danger/10",   chipText: "text-danger" },
  MEDIUM: { border: "border-l-warning",  label: "MEDIUM", chipBg: "bg-warning/10",  chipText: "text-warning" },
  LOW:    { border: "border-l-primary",  label: "LOW",    chipBg: "bg-primary/10",  chipText: "text-primary" },
  INFO:   { border: "border-l-text-muted", label: "INFO", chipBg: "bg-surface-alt", chipText: "text-text-muted" },
};

export default function FindingsList({ findings }: { findings: Finding[] }) {
  const sorted = [...findings].sort((a, b) => SEV_ORDER[a.severity] - SEV_ORDER[b.severity] || b.score - a.score);

  return (
    <div>
      <div className="mb-3 flex items-baseline justify-between">
        <h3 className="font-display text-2xl text-text">Findings</h3>
        <span className="text-[11px] uppercase tracking-[0.14em] text-text-muted">
          {findings.length} flagged
        </span>
      </div>
      <ol className="space-y-3">
        {sorted.map((f) => {
          const tone = SEV_TONE[f.severity];
          return (
            <li
              key={f.id}
              className={`rounded-md border border-border border-l-2 bg-surface px-4 py-4 ${tone.border}`}
            >
              <div className="flex items-start gap-3">
                <span
                  aria-hidden
                  className="mt-1.5 inline-block h-2.5 w-2.5 shrink-0 rounded-full bg-accent shadow-[0_0_0_2px_rgba(255,221,0,0.2)]"
                />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                    <div className="font-mono text-[12px] uppercase tracking-wide text-text">
                      {f.pattern_name.replace(/_/g, " ")}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`rounded-sm px-1.5 py-0.5 text-[10px] font-semibold ${tone.chipBg} ${tone.chipText}`}>
                        {tone.label}
                      </span>
                      <span className="tabular font-mono text-[11px] text-text-muted">
                        {f.score}/10
                      </span>
                    </div>
                  </div>
                  <p className="mt-1.5 text-[13.5px] leading-relaxed text-text/90">{f.description}</p>
                  {f.evidence_ids.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5 text-[11px] text-text-muted">
                      <span className="uppercase tracking-[0.12em]">cites</span>
                      {f.evidence_ids.map((id) => (
                        <code key={id} className="rounded-sm bg-surface-alt px-1.5 py-0.5 font-mono text-[11px] text-text">
                          {id}
                        </code>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
