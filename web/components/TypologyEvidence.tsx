"use client";

import { useMemo, useState } from "react";
import { BookOpen, ChevronLeft, ChevronRight } from "lucide-react";
import type { TypologyChunk } from "@/lib/types";

const HIGHLIGHT_KEYWORDS = [
  "linked",
  "structured to avoid",
  "single transaction",
  "enhanced CDD",
  "higher risk",
  "beneficial ownership",
  "misuse of legal persons",
];

function highlight(text: string): React.ReactNode[] {
  let result: React.ReactNode[] = [text];
  HIGHLIGHT_KEYWORDS.forEach((kw, idx) => {
    const next: React.ReactNode[] = [];
    result.forEach((part) => {
      if (typeof part !== "string") {
        next.push(part);
        return;
      }
      const segments = part.split(new RegExp(`(${kw})`, "i"));
      segments.forEach((seg, i) => {
        if (i % 2 === 1) {
          next.push(
            <span
              key={`h-${idx}-${i}-${seg}`}
              className="border-b border-secondary bg-secondary-fixed/50 px-1 font-sans font-semibold not-italic"
            >
              {seg}
            </span>,
          );
        } else if (seg) {
          next.push(seg);
        }
      });
    });
    result = next;
  });
  return result;
}

export default function TypologyEvidence({ chunks }: { chunks: TypologyChunk[] }) {
  const sorted = useMemo(
    () => [...chunks].sort((a, b) => b.similarity_score - a.similarity_score),
    [chunks],
  );
  const [idx, setIdx] = useState(0);
  const active = sorted[idx];

  if (!active) return null;

  const prev = () => setIdx((i) => Math.max(0, i - 1));
  const next = () => setIdx((i) => Math.min(sorted.length - 1, i + 1));

  return (
    <div className="flex h-full flex-col rounded border border-outline-variant/30 bg-[#e4e5e6] p-5">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BookOpen size={16} strokeWidth={1.75} className="text-tertiary-container" />
          <span className="text-xs font-bold uppercase tracking-wider text-on-surface">
            Citation Viewer
          </span>
        </div>
        <span className="rounded border border-[#a8aaac]/40 bg-[#c4c6c8] px-2 py-1 font-mono text-[10px] font-bold tracking-wider text-on-surface">
          REF: {active.id.toUpperCase()}
        </span>
      </div>

      <div className="mb-4">
        <div className="mb-1 text-[10px] font-bold uppercase tracking-wider text-on-surface-variant">
          Source Directive
        </div>
        <div className="text-sm font-medium text-on-surface">
          {active.source} · {active.section}
        </div>
        <div className="mt-0.5 text-xs text-on-surface-variant">{active.title}</div>
      </div>

      <div className="relative flex-1 overflow-hidden rounded border border-outline-variant/20 bg-white shadow-sm">
        <div className="h-1 w-full bg-tertiary-container" />
        <div className="relative p-5">
          <div className="absolute left-0 top-0 h-full w-1 bg-tertiary-container" />
          <p className="font-serif text-sm italic leading-relaxed text-on-surface">
            {highlight(active.text)}
          </p>
        </div>
        <div className="h-px w-full bg-outline-variant/30" />
        <div className="flex items-center justify-between px-5 py-2 text-[10px] font-mono text-on-surface-variant">
          <span>{active.source}</span>
          <span>{active.section}</span>
        </div>
      </div>

      {sorted.length > 1 && (
        <div className="mt-3 flex items-center justify-between">
          <button
            type="button"
            onClick={prev}
            disabled={idx === 0}
            className="flex items-center gap-1 text-xs text-on-surface-variant transition-colors hover:text-on-surface disabled:opacity-30"
          >
            <ChevronLeft size={14} strokeWidth={1.75} />
            Prev
          </button>
          <span className="font-mono text-[11px] text-on-surface-variant">
            {idx + 1} / {sorted.length} · sim {Math.round(active.similarity_score * 100)}%
          </span>
          <button
            type="button"
            onClick={next}
            disabled={idx === sorted.length - 1}
            className="flex items-center gap-1 text-xs text-on-surface-variant transition-colors hover:text-on-surface disabled:opacity-30"
          >
            Next
            <ChevronRight size={14} strokeWidth={1.75} />
          </button>
        </div>
      )}
    </div>
  );
}
