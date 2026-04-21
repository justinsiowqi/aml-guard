"use client";

import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { Network, ScanSearch, BookOpenCheck, Database, ReceiptText, Check, Loader2 } from "lucide-react";
import type { InvestigationStep, ToolName } from "@/lib/types";

const TOOL_META: Record<ToolName, { label: string; icon: typeof Network; tint: string }> = {
  traverse_entity_network:   { label: "traverse_entity_network",   icon: Network,       tint: "bg-primary/10 text-primary" },
  detect_graph_anomalies:    { label: "detect_graph_anomalies",    icon: ScanSearch,    tint: "bg-danger/10 text-danger" },
  retrieve_typology_chunks:  { label: "retrieve_typology_chunks",  icon: BookOpenCheck, tint: "bg-warning/10 text-warning" },
  persist_case_finding:      { label: "persist_case_finding",      icon: Database,      tint: "bg-success/10 text-success" },
  trace_evidence:            { label: "trace_evidence",            icon: ReceiptText,   tint: "bg-text/10 text-text" },
};

const MIN_RUNNING_MS = 800;

export default function InvestigationStream({
  steps,
  isStreaming,
}: {
  steps: InvestigationStep[];
  isStreaming: boolean;
}) {
  const empty = steps.length === 0;
  const [doneMask, setDoneMask] = useState<boolean[]>(() => steps.map(() => false));

  useEffect(() => {
    setDoneMask(steps.map(() => false));
    const timers: ReturnType<typeof setTimeout>[] = [];
    const now = Date.now();
    steps.forEach((step, i) => {
      const tsMs = new Date(step.timestamp).getTime();
      const delay = Math.max(MIN_RUNNING_MS, tsMs - now);
      const t = setTimeout(() => {
        setDoneMask((prev) => {
          const next = [...prev];
          next[i] = true;
          return next;
        });
      }, delay);
      timers.push(t);
    });
    return () => timers.forEach((t) => clearTimeout(t));
  }, [steps]);

  const doneCount = doneMask.filter(Boolean).length;
  const allDone = !empty && doneCount === steps.length;
  const completed = !isStreaming && allDone;

  return (
    <div>
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h3 className="font-display text-sm text-text-muted">Agent run</h3>
        {!empty && !allDone && (
          <div className="flex items-center gap-2 rounded-sm bg-surface-alt px-2 py-0.5 text-[11px] text-text-muted">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-60" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-accent" />
            </span>
            <span className="tabular font-mono">
              {doneCount} / {steps.length} complete
            </span>
          </div>
        )}
        {completed && (
          <motion.div
            initial={{ opacity: 0, y: -2 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, ease: "easeOut" }}
            className="flex items-center gap-1.5 rounded-sm bg-success/10 px-2 py-0.5 text-[11px] font-medium text-success"
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
        <motion.div
          initial="hidden"
          animate="show"
          variants={{ show: { transition: { staggerChildren: 0.08 } } }}
          className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5"
        >
          {steps.map((step, i) => {
            const meta = TOOL_META[step.tool] ?? TOOL_META.trace_evidence;
            const Icon = meta.icon;
            const done = doneMask[i] ?? false;
            return (
              <motion.div
                key={`${step.tool}-${i}`}
                variants={{
                  hidden: { opacity: 0, y: 6 },
                  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: "easeOut" } },
                }}
                className={`flex h-full min-h-[170px] flex-col rounded-md border bg-surface px-3.5 py-3 transition-colors ${
                  done ? "border-border" : "border-accent/50 shadow-[0_0_0_3px_rgba(255,221,0,0.08)]"
                }`}
              >
                <div className="flex items-center gap-2">
                  <div className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-sm ${meta.tint}`}>
                    <Icon size={14} strokeWidth={1.75} />
                  </div>
                  <StatusBadge done={done} timestamp={step.timestamp} />
                </div>
                <code className="mt-2 block truncate text-[11.5px] font-medium text-text" title={meta.label}>
                  {meta.label}
                </code>
                <p className="mt-1 line-clamp-3 text-[12.5px] leading-relaxed text-text/80">
                  {step.summary}
                </p>
                {step.cypher_used && (
                  <details className="group mt-auto pt-2">
                    <summary className="cursor-pointer select-none text-[10.5px] uppercase tracking-[0.12em] text-text-muted transition-colors hover:text-text">
                      cypher
                    </summary>
                    <pre className="mt-2 overflow-x-auto rounded-sm bg-surface-alt px-3 py-2 font-mono text-[11px] leading-relaxed text-text/90">
                      {step.cypher_used}
                    </pre>
                  </details>
                )}
              </motion.div>
            );
          })}
        </motion.div>
      )}
    </div>
  );
}

function StatusBadge({ done, timestamp }: { done: boolean; timestamp: string }) {
  if (done) {
    return (
      <span className="ml-auto flex items-center gap-1 text-[10.5px] text-success">
        <Check size={11} strokeWidth={2.25} />
        <span className="tabular font-mono text-text-muted">{formatTime(timestamp)}</span>
      </span>
    );
  }
  return (
    <span className="ml-auto flex items-center gap-1 text-[10.5px]">
      <Loader2 size={11} strokeWidth={2} className="animate-spin text-text" />
      <span className="uppercase tracking-[0.12em] text-text-muted">running</span>
    </span>
  );
}

const TIME_FMT = new Intl.DateTimeFormat("en-GB", {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
  timeZone: "Asia/Singapore",
});

function formatTime(iso: string): string {
  try {
    return `${TIME_FMT.format(new Date(iso))} +08`;
  } catch {
    return iso;
  }
}
