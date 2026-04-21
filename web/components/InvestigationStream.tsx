"use client";

import { motion, AnimatePresence } from "framer-motion";
import { useEffect, useState } from "react";
import type { InvestigationStep, ToolName } from "@/lib/types";

type Tone = "primary" | "error";

const TOOL_TITLE: Record<ToolName, string> = {
  traverse_entity_network: "Entity Resolution",
  detect_graph_anomalies: "Typology Matching",
  retrieve_typology_chunks: "Evidence Retrieval",
  persist_case_finding: "Case Persistence",
  trace_evidence: "Transaction Monitoring",
};

const TOOL_TONE: Record<ToolName, Tone> = {
  traverse_entity_network: "primary",
  detect_graph_anomalies: "primary",
  retrieve_typology_chunks: "primary",
  persist_case_finding: "primary",
  trace_evidence: "primary",
};

const DOT_TONE: Record<Tone, string> = {
  primary: "bg-primary",
  error: "bg-error",
};

const TITLE_TONE: Record<Tone, string> = {
  primary: "text-on-surface",
  error: "text-error",
};

const MIN_RUNNING_MS = 600;

export default function InvestigationStream({
  steps,
  isStreaming,
}: {
  steps: InvestigationStep[];
  isStreaming: boolean;
}) {
  const [revealedCount, setRevealedCount] = useState(0);

  useEffect(() => {
    setRevealedCount(0);
    if (!steps.length) return;
    const timers: ReturnType<typeof setTimeout>[] = [];
    const now = Date.now();
    steps.forEach((step, i) => {
      const tsMs = new Date(step.timestamp).getTime();
      const delay = Math.max(MIN_RUNNING_MS, tsMs - now);
      timers.push(setTimeout(() => setRevealedCount((c) => Math.max(c, i + 1)), delay));
    });
    return () => timers.forEach(clearTimeout);
  }, [steps]);

  const visible = isStreaming ? steps.slice(0, revealedCount) : steps;

  return (
    <div className="h-full rounded bg-surface-container-low p-6">
      <div className="mb-4 flex items-center justify-between border-b border-outline-variant/20 pb-2">
        <h3 className="text-sm font-bold uppercase tracking-wider text-on-surface">
          Investigation Stream
        </h3>
        {isStreaming && (
          <span className="flex items-center gap-1.5 font-mono text-[11px] text-on-surface-variant">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-60" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-accent" />
            </span>
            {revealedCount}/{steps.length}
          </span>
        )}
      </div>

      {visible.length === 0 ? (
        <div className="rounded border border-dashed border-outline-variant/40 bg-surface-container-lowest px-4 py-6 text-sm text-on-surface-variant">
          Reading graph schema, preparing Cypher…
        </div>
      ) : (
        <ol className="relative space-y-6 pl-4">
          <div className="absolute bottom-2 left-1.5 top-2 w-px bg-outline-variant/30" />
          <AnimatePresence initial={false}>
            {visible.map((step, i) => {
              const tone = TOOL_TONE[step.tool] ?? "primary";
              const title = TOOL_TITLE[step.tool] ?? step.tool;
              return (
                <motion.li
                  key={`${step.tool}-${i}`}
                  initial={{ opacity: 0, x: -4 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.3, ease: "easeOut" }}
                  className="relative"
                >
                  <div
                    className={`absolute -left-[18px] top-0 h-3 w-3 rounded-full ring-4 ring-surface-container-low ${DOT_TONE[tone]}`}
                  />
                  <div className="mb-1 font-mono text-xs text-on-surface-variant">
                    {formatTime(step.timestamp)}
                  </div>
                  <div className={`text-sm font-bold ${TITLE_TONE[tone]}`}>{title}</div>
                  <div className="mt-1 text-xs text-on-surface-variant">{step.summary}</div>
                  {step.cited_chunks && step.cited_chunks.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap items-center gap-1 text-[10px]">
                      <span className="uppercase tracking-[0.14em] text-on-surface-variant">
                        cites
                      </span>
                      {step.cited_chunks.map((id) => (
                        <code
                          key={id}
                          className="rounded-sm bg-surface-container px-1.5 py-0.5 font-mono text-[10px] text-on-surface"
                        >
                          {id}
                        </code>
                      ))}
                    </div>
                  )}
                </motion.li>
              );
            })}
          </AnimatePresence>
        </ol>
      )}
    </div>
  );
}

const TIME_FMT = new Intl.DateTimeFormat("en-GB", {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
  timeZone: "UTC",
});

function formatTime(iso: string): string {
  try {
    return `${TIME_FMT.format(new Date(iso))} Z`;
  } catch {
    return iso;
  }
}
