import type { InvestigationStep, ToolName } from "@/lib/types";
import { Network, ScanSearch, BookOpenCheck, Database, ReceiptText } from "lucide-react";

const TOOL_ICON: Record<ToolName, typeof Network> = {
  traverse_entity_network: Network,
  detect_graph_anomalies: ScanSearch,
  retrieve_typology_chunks: BookOpenCheck,
  persist_case_finding: Database,
  trace_evidence: ReceiptText,
};

export default function InvestigationTimeline({ steps }: { steps: InvestigationStep[] }) {
  return (
    <div>
      <div className="mb-3 flex items-baseline justify-between">
        <h3 className="font-display text-2xl text-text">Audit trail</h3>
        <span className="text-[11px] uppercase tracking-[0.14em] text-text-muted">
          Cypher + citations
        </span>
      </div>
      <ol className="relative border-l border-border pl-5">
        {steps.map((step, i) => {
          const Icon = TOOL_ICON[step.tool] ?? ReceiptText;
          return (
            <li key={`${step.tool}-${i}`} className="relative pb-5 last:pb-0">
              <span className="absolute -left-[29px] top-0 flex h-6 w-6 items-center justify-center rounded-full border border-border bg-surface">
                <Icon size={12} strokeWidth={1.75} className="text-text" />
              </span>
              <div className="flex items-baseline justify-between gap-3">
                <code className="text-[12px] font-medium text-text">{step.tool}</code>
                <time className="tabular font-mono text-[11px] text-text-muted">
                  {formatTime(step.timestamp)}
                </time>
              </div>
              <p className="mt-1 text-[13px] leading-relaxed text-text/90">{step.summary}</p>
              {step.cypher_used && (
                <pre className="mt-2 overflow-x-auto rounded-sm bg-surface-alt px-3 py-2 font-mono text-[11px] leading-relaxed text-text/90">
                  {step.cypher_used}
                </pre>
              )}
              {step.cited_chunks && step.cited_chunks.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5 text-[11px] text-text-muted">
                  <span className="uppercase tracking-[0.12em]">cites</span>
                  {step.cited_chunks.map((id) => (
                    <code key={id} className="rounded-sm bg-surface-alt px-1.5 py-0.5 font-mono text-[11px] text-text">
                      {id}
                    </code>
                  ))}
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toISOString().substring(11, 19) + "Z";
  } catch {
    return iso;
  }
}
