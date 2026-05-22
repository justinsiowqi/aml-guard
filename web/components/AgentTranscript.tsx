"use client";

import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Bot,
  ChevronDown,
  FileText,
  Code2,
  Loader2,
  Sparkles,
  Wrench,
} from "lucide-react";
import type { AgentTranscriptEvent } from "@/lib/types";

/**
 * Extract MCP tool calls from a code block so they can be displayed as
 * structured chips rather than raw Python.  Looks for the pattern:
 *   claude_tool_runner(tool_name="foo", tool_args={...})
 * or positional calls like claude_tool_runner("foo", {...}).
 */
function extractToolCall(code: string | null): { name: string; args: string } | null {
  if (!code) return null;
  const m = code.match(
    /claude_tool_runner\s*\(\s*(?:tool_name\s*=\s*)?["']([^"']+)["']\s*,\s*(?:tool_args\s*=\s*)?(\{[\s\S]*?\})/
  );
  if (!m) return null;
  try {
    // Pretty-print the args object for readability.
    const pretty = JSON.stringify(JSON.parse(m[2].replace(/'/g, '"')), null, 2);
    return { name: m[1], args: pretty };
  } catch {
    return { name: m[1], args: m[2] };
  }
}

/**
 * Defensive frontend filter — backend src/api/jobs.py already strips
 * housekeeping turns (synthesises titles from turn_message content), but if
 * a noise title ever slips through we'd rather drop it than render it.
 */
const NOISE_TITLE_PATTERNS: RegExp[] = [
  /^executing\s+python\s+code\s+block$/i,
  /^agent\s+working$/i,
  /^agent\s+setting\s+up\s+environment$/i,
  /^agent\s+(initiating|starting)/i,
  /^checking\s+(available\s+)?mcp/i,
];

function isNoise(ev: AgentTranscriptEvent): boolean {
  if (ev.kind !== "turn") return false;
  return NOISE_TITLE_PATTERNS.some((p) => p.test(ev.title.trim()));
}

/**
 * Renders the live transcript of the H2OGPTe Coder Agent loop during deep
 * analysis. Each card is one of:
 *   - "agent_analysis"  (the agent's overall plan, pinned to the top)
 *   - "turn"            (one turn of the agent loop, ordered by turn_idx)
 *   - "final_summary"   (run cost / timing, pinned to the bottom)
 *
 * Lives in its own full-width section below the verdict row; deliberately
 * separate from the Investigation Stream component (which stays for the
 * deterministic + narrator path).
 */
export default function AgentTranscript({
  events,
  isRunning,
  elapsedSeconds,
  phaseLabel,
}: {
  events: AgentTranscriptEvent[];
  isRunning: boolean;
  elapsedSeconds: number;
  phaseLabel: string;
}) {
  const ordered = useMemo(() => {
    // Drop housekeeping turns, then sort so the agent plan (turn_idx -1) is
    // first, the actual step turns in order, and final_summary (turn_idx 999)
    // is last. Backend may return them in any order — H2OGPTe's type_list
    // isn't strictly chronological.
    //
    // Re-number visible turns 1..N based on display order. The backend's
    // `turn_idx` has gaps wherever we dropped housekeeping turns, and gaps
    // are confusing to the reader ("Turn 1, Turn 4, Turn 7…").
    const filtered = events
      .filter((ev) => !isNoise(ev))
      .sort((a, b) => a.turn_idx - b.turn_idx);
    let displayTurn = 0;
    return filtered.map((ev) => ({
      ...ev,
      displayTurn: ev.kind === "turn" ? ++displayTurn : null,
    }));
  }, [events]);

  const filteredOutCount = events.length - ordered.length;

  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const toggle = (id: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  if (ordered.length === 0 && !isRunning) return null;

  return (
    <section className="mb-6 rounded border border-surface-container bg-surface-container-lowest p-5">
      <header className="mb-4 flex items-center justify-between border-b border-surface-container-high pb-3">
        <div className="flex items-center gap-2">
          <Bot size={16} strokeWidth={2} className="text-primary" />
          <h3 className="text-sm font-bold uppercase tracking-wider text-on-surface">
            Agent Reasoning
          </h3>
          <span className="rounded-sm bg-primary-fixed/40 px-1.5 py-0.5 text-[9.5px] font-semibold uppercase tracking-wider text-on-primary-fixed-variant">
            H2OGPTe
          </span>
        </div>
        <div className="flex items-center gap-3 text-[11px] text-on-surface-variant">
          {isRunning && (
            <span className="flex items-center gap-1.5 font-mono">
              <Loader2 size={11} strokeWidth={2.5} className="animate-spin text-primary" />
              <span className="italic">{phaseLabel}</span>
            </span>
          )}
          <span className="font-mono tabular-nums">{elapsedSeconds}s</span>
          <span className="font-mono tabular-nums">
            {ordered.length} event{ordered.length === 1 ? "" : "s"}
            {filteredOutCount > 0 && (
              <span className="ml-1 text-on-surface-variant/60">+{filteredOutCount} housekeeping</span>
            )}
          </span>
        </div>
      </header>

      {ordered.length === 0 ? (
        <div className="rounded border border-dashed border-outline-variant/40 px-4 py-6 text-center text-xs text-on-surface-variant">
          Waiting for the H2OGPTe agent to emit its first turn…
        </div>
      ) : (
        <ol className="space-y-3">
          <AnimatePresence initial={false}>
            {ordered.map((ev) => {
              const isOpen = expanded.has(ev.id);
              const Icon = ev.kind === "agent_analysis" ? Sparkles : ev.kind === "final_summary" ? FileText : Code2;
              const tone =
                ev.kind === "agent_analysis"
                  ? "border-secondary/40 bg-secondary-fixed/20"
                  : ev.kind === "final_summary"
                  ? "border-primary/40 bg-primary-fixed/20"
                  : "border-surface-container-high bg-surface-container-low";
              const turnLabel =
                ev.kind === "turn"
                  ? `Turn ${ev.displayTurn}`
                  : ev.kind === "agent_analysis"
                  ? "Plan"
                  : "Final";
              return (
                <motion.li
                  key={ev.id}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.25, ease: "easeOut" }}
                  className={`rounded border px-4 py-3 ${tone}`}
                >
                  <button
                    type="button"
                    onClick={() => toggle(ev.id)}
                    className="flex w-full items-start gap-3 text-left"
                  >
                    <Icon size={14} strokeWidth={2.25} className="mt-0.5 shrink-0 text-primary" />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-on-surface-variant">
                        <span>{turnLabel}</span>
                        {ev.files.length > 0 && (
                          <span className="rounded-sm bg-surface-container-high px-1.5 py-0.5 text-[9.5px] font-semibold text-on-surface-variant">
                            {ev.files.length} file{ev.files.length === 1 ? "" : "s"}
                          </span>
                        )}
                        {ev.code && (
                          <span className="rounded-sm bg-surface-container-high px-1.5 py-0.5 text-[9.5px] font-semibold text-on-surface-variant">
                            code
                          </span>
                        )}
                      </div>
                      <div className="mt-0.5 text-[13.5px] font-semibold leading-snug text-on-surface">
                        {ev.title}
                      </div>
                      {!isOpen && ev.message && (
                        <div
                          className="mt-1 text-[12px] leading-snug text-on-surface-variant"
                          style={{
                            display: "-webkit-box",
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: "vertical",
                            overflow: "hidden",
                          }}
                        >
                          {ev.message}
                        </div>
                      )}
                    </div>
                    <ChevronDown
                      size={14}
                      strokeWidth={2}
                      className={`mt-1 shrink-0 text-on-surface-variant transition-transform ${isOpen ? "rotate-180" : ""}`}
                    />
                  </button>
                  {isOpen && (() => {
                    const toolCall = extractToolCall(ev.code ?? null);
                    return (
                      <div className="mt-3 space-y-3 border-t border-surface-container-high pt-3">
                        {ev.message && (
                          <div className="whitespace-pre-wrap text-[12.5px] leading-relaxed text-on-surface">
                            {ev.message}
                          </div>
                        )}

                        {/* Structured tool-call block — extracted from the code dict */}
                        {toolCall && (
                          <div className="rounded border border-primary/25 bg-primary-fixed/10 px-3 py-2.5">
                            <div className="mb-1.5 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-on-primary-fixed-variant">
                              <Wrench size={11} strokeWidth={2.5} />
                              MCP Tool Call
                            </div>
                            <div className="mb-1.5 font-mono text-[11.5px] font-semibold text-on-surface">
                              {toolCall.name}
                            </div>
                            <pre className="max-h-40 overflow-auto rounded bg-surface-container-lowest px-2 py-1.5 font-mono text-[10.5px] leading-snug text-on-surface-variant">
                              {toolCall.args}
                            </pre>
                          </div>
                        )}

                        {/* Raw code — only shown when no tool call was extracted */}
                        {ev.code && !toolCall && (
                          <div>
                            <div className="mb-1 text-[10px] font-bold uppercase tracking-wider text-on-surface-variant">
                              Code
                            </div>
                            <pre className="max-h-48 overflow-auto rounded bg-surface-container-lowest p-2 font-mono text-[10.5px] leading-snug text-on-surface-variant">
                              {ev.code}
                            </pre>
                          </div>
                        )}

                        {ev.files.length > 0 && (
                          <div>
                            <div className="mb-1 text-[10px] font-bold uppercase tracking-wider text-on-surface-variant">
                              Artifacts
                            </div>
                            <ul className="space-y-0.5 font-mono text-[10.5px] text-on-surface-variant">
                              {ev.files.map((f, i) => (
                                <li key={`${ev.id}-f-${i}`}>{f}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    );
                  })()}
                </motion.li>
              );
            })}
          </AnimatePresence>
        </ol>
      )}
    </section>
  );
}
