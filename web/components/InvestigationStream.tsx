"use client";

import { motion } from "framer-motion";
import { Network, ScanSearch, BookOpenCheck, Database, ReceiptText, Check } from "lucide-react";
import type { InvestigationStep, ToolName } from "@/lib/types";

const TOOL_META: Record<ToolName, { label: string; icon: typeof Network; tint: string }> = {
  traverse_entity_network:   { label: "traverse_entity_network",   icon: Network,       tint: "bg-primary/10 text-primary" },
  detect_graph_anomalies:    { label: "detect_graph_anomalies",    icon: ScanSearch,    tint: "bg-danger/10 text-danger" },
  retrieve_typology_chunks:  { label: "retrieve_typology_chunks",  icon: BookOpenCheck, tint: "bg-warning/10 text-warning" },
  persist_case_finding:      { label: "persist_case_finding",      icon: Database,      tint: "bg-success/10 text-success" },
  trace_evidence:            { label: "trace_evidence",            icon: ReceiptText,   tint: "bg-text/10 text-text" },
};

export default function InvestigationStream({
  steps,
  isStreaming,
}: {
  steps: InvestigationStep[];
  isStreaming: boolean;
}) {
  const empty = steps.length === 0;
  const completed = !isStreaming && !empty;

  return (
    <div>
      <div className="mb-3 flex items-center gap-3">
        <div className="text-[11px] uppercase tracking-[0.16em] text-text-muted">
          Agent run
        </div>
        {isStreaming && (
          <div className="flex items-center gap-1.5 text-[11px] text-text-muted">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-60" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-accent" />
            </span>
            investigating…
          </div>
        )}
        {completed && (
          <motion.div
            initial={{ opacity: 0, y: -2 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, ease: "easeOut" }}
            className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-[0.12em] text-success"
          >
            <Check size={12} strokeWidth={2.25} />
            agent completed
          </motion.div>
        )}
      </div>

      {empty ? (
        <div className="rounded-md border border-dashed border-border bg-surface px-4 py-6 text-sm text-text-muted">
          Reading graph schema, preparing Cypher…
        </div>
      ) : (
        <motion.ol
          initial="hidden"
          animate="show"
          variants={{ show: { transition: { staggerChildren: 0.45 } } }}
          className="space-y-2"
        >
          {steps.map((step, i) => {
            const meta = TOOL_META[step.tool] ?? TOOL_META.trace_evidence;
            const Icon = meta.icon;
            return (
              <motion.li
                key={`${step.tool}-${i}`}
                variants={{
                  hidden: { opacity: 0, y: 6 },
                  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: "easeOut" } },
                }}
                className="rounded-md border border-border bg-surface px-4 py-3"
              >
                <div className="flex items-start gap-3">
                  <div className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-sm ${meta.tint}`}>
                    <Icon size={14} strokeWidth={1.75} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline justify-between gap-3">
                      <code className="text-[12px] font-medium text-text">{meta.label}</code>
                      <time className="tabular text-[11px] text-text-muted">
                        {formatTime(step.timestamp)}
                      </time>
                    </div>
                    <p className="mt-1 text-[13.5px] leading-relaxed text-text/90">{step.summary}</p>
                    {step.cypher_used && (
                      <details className="group mt-2">
                        <summary className="cursor-pointer select-none text-[11px] uppercase tracking-[0.12em] text-text-muted transition-colors hover:text-text">
                          cypher
                        </summary>
                        <pre className="mt-2 overflow-x-auto rounded-sm bg-surface-alt px-3 py-2 font-mono text-[11.5px] leading-relaxed text-text/90">
                          {step.cypher_used}
                        </pre>
                      </details>
                    )}
                  </div>
                </div>
              </motion.li>
            );
          })}
        </motion.ol>
      )}
    </div>
  );
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toISOString().substring(11, 19) + "Z";
  } catch {
    return iso;
  }
}
