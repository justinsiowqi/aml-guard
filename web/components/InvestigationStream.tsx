"use client";

import { motion, AnimatePresence } from "framer-motion";
import { useEffect, useState } from "react";
import { ChevronDown, Loader2 } from "lucide-react";
import type { InvestigationStep, ToolName } from "@/lib/types";

type Tone = "primary" | "error";

const TOOL_TITLE: Record<ToolName, string> = {
  traverse_entity_network: "Entity Resolution",
  detect_graph_anomalies: "Typology Matching",
  retrieve_typology_chunks: "Evidence Retrieval",
  trace_evidence: "Transaction Monitoring",
  narrative_synthesis: "Narrative Synthesis",
};

const TOOL_TONE: Record<ToolName, Tone> = {
  traverse_entity_network: "primary",
  detect_graph_anomalies: "primary",
  retrieve_typology_chunks: "primary",
  trace_evidence: "primary",
  narrative_synthesis: "primary",
};

const NARRATIVE_THOUGHTS = [
  "Composing analyst headline from fired typologies…",
  "Cross-referencing top regulatory citations…",
  "Drafting per-finding narratives with H2OGPTe…",
  "Summarising risk decomposition for handover…",
  "Generating recommended actions list…",
  "Validating evidence-grounded claims…",
];

const GENERIC_THOUGHTS = [
  "Polling tool result…",
  "Parsing response payload…",
  "Updating evidence ledger…",
];

const THOUGHT_INTERVAL_MS = 1800;

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
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [thoughtIdx, setThoughtIdx] = useState(0);

  const toggleExpanded = (i: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  };

  useEffect(() => {
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

  // Cycle the rolling thought messages on the active step while still streaming.
  useEffect(() => {
    if (!isStreaming) return;
    setThoughtIdx(0);
    const id = setInterval(
      () => setThoughtIdx((i) => i + 1),
      THOUGHT_INTERVAL_MS,
    );
    return () => clearInterval(id);
  }, [isStreaming, revealedCount]);

  const visible = isStreaming ? steps.slice(0, revealedCount) : steps;
  const activeIdx = isStreaming ? revealedCount - 1 : -1;

  const runningThought = (step: InvestigationStep): string => {
    const pool =
      step.tool === "narrative_synthesis" ? NARRATIVE_THOUGHTS : GENERIC_THOUGHTS;
    return pool[thoughtIdx % pool.length];
  };

  return (
    <div className="flex h-full max-h-[380px] flex-col rounded bg-[#edeeef] p-6">
      <div className="mb-4 flex shrink-0 items-center justify-between border-b border-outline-variant/20 pb-2">
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
        <ol className="relative flex-1 space-y-6 overflow-y-auto pl-6 pr-4 [scrollbar-gutter:stable]">
          <div className="absolute bottom-2 left-3 top-2 w-px bg-outline-variant/30" />
          <AnimatePresence initial={false}>
            {visible.map((step, i) => {
              const tone = TOOL_TONE[step.tool] ?? "primary";
              const title = TOOL_TITLE[step.tool] ?? step.tool;
              const isExpanded = expanded.has(i);
              return (
                <motion.li
                  key={`${step.tool}-${i}`}
                  initial={{ opacity: 0, x: -4 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.3, ease: "easeOut" }}
                  className="relative"
                >
                  <div
                    className={`absolute -left-[18px] top-0 h-3 w-3 rounded-full ring-4 ring-[#edeeef] ${DOT_TONE[tone]} ${i === activeIdx ? "animate-pulse" : ""}`}
                  />
                  <div className="mb-1 flex items-center gap-2 font-mono text-xs text-on-surface-variant">
                    <span>{formatTime(step.timestamp)}</span>
                    {i === activeIdx && (
                      <Loader2
                        size={11}
                        strokeWidth={2.5}
                        className="animate-spin text-primary"
                      />
                    )}
                  </div>
                  <div className={`text-sm font-bold ${TITLE_TONE[tone]}`}>{title}</div>
                  {isStreaming ? (
                    <div className="mt-1 text-xs text-on-surface-variant">
                      {i === activeIdx ? (
                        <span className="italic text-primary">
                          {runningThought(step)}
                        </span>
                      ) : (
                        step.summary
                      )}
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => toggleExpanded(i)}
                      className="mt-1 flex w-full items-start gap-1 text-left text-xs text-on-surface-variant transition-colors hover:text-on-surface"
                    >
                      <span
                        style={
                          isExpanded
                            ? undefined
                            : {
                                display: "-webkit-box",
                                WebkitLineClamp: 2,
                                WebkitBoxOrient: "vertical",
                                overflow: "hidden",
                              }
                        }
                      >
                        {step.summary}
                      </span>
                      <ChevronDown
                        size={14}
                        strokeWidth={2}
                        className={`mt-0.5 shrink-0 transition-transform ${isExpanded ? "rotate-180" : ""}`}
                      />
                    </button>
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
