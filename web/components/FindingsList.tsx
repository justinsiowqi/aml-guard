"use client";

import { Fragment, useState } from "react";
import type { Finding, Severity, TypologyChunk } from "@/lib/types";
import { ChevronDown, Filter } from "lucide-react";

const SEV_ORDER: Record<Severity, number> = { HIGH: 0, MEDIUM: 1, LOW: 2, INFO: 3 };

const SEV_PILL: Record<Severity, { label: string; classes: string }> = {
  HIGH:   { label: "Critical", classes: "bg-[#ba1a1a] text-white" },
  MEDIUM: { label: "High",     classes: "bg-[#872d00] text-white" },
  LOW:    { label: "Moderate", classes: "bg-[#00288e] text-white" },
  INFO:   { label: "Info",     classes: "bg-[#757684] text-white" },
};

function patternCode(name: string): string {
  return name
    .split("_")
    .map((w) => w.slice(0, 3).toUpperCase())
    .slice(0, 2)
    .join("-");
}

function titleCase(name: string): string {
  return name
    .split("_")
    .map((w) => (w ? w[0].toUpperCase() + w.slice(1) : w))
    .join(" ");
}

function ChunkCard({ chunk }: { chunk: TypologyChunk }) {
  const [expanded, setExpanded] = useState(false);
  const hasMore =
    !!chunk.text_full && chunk.text_full.length > chunk.text.length;
  const shown = expanded && chunk.text_full ? chunk.text_full : chunk.text;

  return (
    <li className="flex min-w-[240px] flex-1 basis-64 items-start gap-3 rounded border border-outline-variant/30 bg-surface-container-lowest px-3 py-2 text-xs">
      <div className="min-w-0 flex-1">
        <div className="font-mono text-[10px] uppercase tracking-wider text-on-surface-variant">
          {chunk.source} · {chunk.section}
        </div>
        <div className="mt-0.5 font-semibold text-on-surface">
          {chunk.title}
        </div>
        <p
          className={`mt-1.5 leading-snug text-on-surface-variant ${
            expanded
              ? "max-h-44 overflow-y-auto rounded border border-outline-variant/30 bg-surface-container-low/40 p-2 pr-3"
              : ""
          }`}
        >
          {shown}
        </p>
        {hasMore && (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="mt-1.5 text-[11px] font-medium text-[#1e40af] transition-opacity hover:opacity-70"
          >
            {expanded ? "Show less" : "Show more"}
          </button>
        )}
      </div>
    </li>
  );
}

export default function FindingsList({
  findings,
  chunks = [],
}: {
  findings: Finding[];
  chunks?: TypologyChunk[];
}) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const chunksById = new Map(chunks.map((c) => [c.id, c]));

  const sorted = [...findings].sort(
    (a, b) => SEV_ORDER[a.severity] - SEV_ORDER[b.severity] || b.score - a.score,
  );

  return (
    <div className="h-full overflow-hidden rounded border border-surface-container bg-surface-container-lowest">
      <div className="flex items-center justify-between border-b border-surface-container-high bg-surface-container-low/50 p-4">
        <h3 className="text-sm font-bold uppercase tracking-wider text-on-surface">
          Critical Findings Ledger
        </h3>
        <button
          type="button"
          className="flex items-center gap-1 text-xs font-bold text-[#1e40af] transition-opacity hover:opacity-70"
        >
          <Filter size={14} strokeWidth={2} />
          Filter
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="border-b border-surface-container-high bg-surface-container-low/20 text-xs font-bold uppercase tracking-wider text-on-surface-variant">
              <th className="w-24 p-3">Pattern ID</th>
              <th className="p-3">Description</th>
              <th className="w-24 p-3">Severity</th>
              <th className="w-20 p-3 text-right">Score</th>
              <th className="w-16 p-3 text-center">Details</th>
            </tr>
          </thead>
          <tbody className="text-sm">
            {sorted.map((f) => {
              const pill = SEV_PILL[f.severity];
              const isOpen = expanded.has(f.id);
              const linkedChunks = f.evidence_ids
                .map((id) => chunksById.get(id))
                .filter((c): c is TypologyChunk => Boolean(c));

              return (
                <Fragment key={f.id}>
                  <tr
                    onClick={() => toggle(f.id)}
                    className={`group cursor-pointer border-b border-surface-container last:border-b-0 transition-colors hover:bg-surface-container-low/50 ${
                      isOpen ? "bg-surface-container-low/40" : ""
                    }`}
                  >
                    <td className="p-3 font-mono text-xs text-on-surface-variant">
                      {patternCode(f.pattern_name)}
                    </td>
                    <td className="p-3 font-medium text-on-surface">
                      <div>{titleCase(f.pattern_name)}</div>
                      <div
                        className={`mt-1 text-xs text-on-surface-variant ${
                          isOpen ? "" : "line-clamp-2"
                        }`}
                      >
                        {f.description}
                      </div>
                    </td>
                    <td className="p-3">
                      <span
                        className={`rounded-sm px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${pill.classes}`}
                      >
                        {pill.label}
                      </span>
                    </td>
                    <td className="p-3 text-right font-mono text-xs">
                      {(f.score / 10).toFixed(2)}
                    </td>
                    <td className="p-3 text-center">
                      <ChevronDown
                        size={18}
                        strokeWidth={2}
                        aria-label={isOpen ? "Collapse" : "Expand"}
                        className={`mx-auto text-[#1e40af] transition-transform ${
                          isOpen ? "rotate-180" : ""
                        }`}
                      />
                    </td>
                  </tr>
                  {isOpen && (
                    <tr className="border-b border-surface-container last:border-b-0 bg-surface-container-low/30">
                      <td colSpan={5} className="px-4 py-3">
                        <div className="mb-2 text-[10px] font-bold uppercase tracking-wider text-on-surface-variant">
                          Cited Evidence
                        </div>
                        {linkedChunks.length === 0 ? (
                          <div className="font-mono text-xs text-on-surface-variant">
                            {f.evidence_ids.length
                              ? f.evidence_ids.join(", ")
                              : "— none recorded —"}
                          </div>
                        ) : (
                          <ul className="flex flex-wrap gap-2">
                            {linkedChunks.map((c) => (
                              <ChunkCard key={c.id} chunk={c} />
                            ))}
                          </ul>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
