import type { Finding, Severity } from "@/lib/types";
import { FileSearch, Filter } from "lucide-react";

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

export default function FindingsList({ findings }: { findings: Finding[] }) {
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
              <th className="w-24 p-3 text-center">Evidence</th>
            </tr>
          </thead>
          <tbody className="text-sm">
            {sorted.map((f) => {
              const pill = SEV_PILL[f.severity];
              return (
                <tr
                  key={f.id}
                  className="group border-b border-surface-container last:border-b-0 hover:bg-surface-container-low/50"
                >
                  <td className="p-3 font-mono text-xs text-on-surface-variant">
                    {patternCode(f.pattern_name)}
                  </td>
                  <td className="p-3 font-medium text-on-surface">
                    <div>{titleCase(f.pattern_name)}</div>
                    <div className="mt-1 line-clamp-2 text-xs text-on-surface-variant">
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
                  <td className="p-3 text-right font-mono text-xs">{(f.score / 10).toFixed(2)}</td>
                  <td className="p-3 text-center">
                    <button
                      type="button"
                      aria-label={`View evidence for ${f.pattern_name}`}
                      className="text-[#1e40af] transition-opacity hover:opacity-70"
                    >
                      <FileSearch size={18} strokeWidth={1.75} />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
