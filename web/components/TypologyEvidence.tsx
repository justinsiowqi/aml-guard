import type { TypologyChunk } from "@/lib/types";
import { Quote } from "lucide-react";

const SOURCE_TONE: Record<string, string> = {
  "MAS Notice 626": "bg-primary/10 text-primary border-primary/20",
  FATF: "bg-danger/10 text-danger border-danger/20",
  AUSTRAC: "bg-warning/10 text-warning border-warning/20",
};

export default function TypologyEvidence({ chunks }: { chunks: TypologyChunk[] }) {
  return (
    <div>
      <div className="mb-3 flex items-baseline justify-between">
        <h3 className="font-display text-2xl text-text">Typology evidence</h3>
        <span className="text-[11px] uppercase tracking-[0.14em] text-text-muted">
          {chunks.length} cited
        </span>
      </div>
      <ul className="space-y-3">
        {chunks.map((c) => {
          const tone = SOURCE_TONE[c.source] ?? "bg-surface-alt text-text border-border";
          const pct = Math.round(c.similarity_score * 100);
          return (
            <li key={c.id} className="rounded-md border border-border bg-surface px-4 py-4">
              <div className="mb-2 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span className={`rounded-sm border px-1.5 py-0.5 text-[10px] font-semibold ${tone}`}>
                    {c.source}
                  </span>
                  <span className="font-mono text-[11px] text-text-muted">{c.section}</span>
                </div>
                <span className="tabular font-mono text-[11px] text-text-muted">
                  sim {pct}%
                </span>
              </div>
              <div className="mb-1 text-[12px] font-medium text-text">{c.title}</div>
              <div className="flex gap-2">
                <Quote size={14} strokeWidth={1.5} className="mt-0.5 shrink-0 text-text-muted" />
                <p className="text-[13px] italic leading-relaxed text-text/80">{c.text}</p>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
