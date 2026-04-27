"use client";

import { useEffect, useState } from "react";
import { Loader2, CheckCircle2 } from "lucide-react";

const STEPS: { label: string; durationMs: number }[] = [
  { label: "Pulling 2-hop entity subgraph from the graph", durationMs: 1200 },
  { label: "Running 6 anomaly patterns against Layer 1", durationMs: 1800 },
  { label: "Retrieving regulatory citations per fired pattern", durationMs: 2500 },
];

export default function InvestigationLoading({ question }: { question: string }) {
  const [activeIdx, setActiveIdx] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let i = 0;
    function advance() {
      if (cancelled) return;
      if (i >= STEPS.length - 1) return;
      const ms = STEPS[i].durationMs;
      const t = setTimeout(() => {
        if (cancelled) return;
        i += 1;
        setActiveIdx(i);
        advance();
      }, ms);
      timers.push(t);
    }
    const timers: ReturnType<typeof setTimeout>[] = [];
    advance();
    return () => {
      cancelled = true;
      timers.forEach(clearTimeout);
    };
  }, []);

  return (
    <div className="mx-auto max-w-3xl py-12">
      <header className="mb-6">
        <div className="mb-1 text-[11px] uppercase tracking-[0.18em] text-on-surface-variant">
          AML Guard · Investigation in progress
        </div>
        <h1 className="text-2xl font-bold leading-tight tracking-tight text-on-surface">
          {question}
        </h1>
      </header>

      <div className="rounded border border-outline-variant/30 bg-surface-container-lowest p-6">
        <ul className="space-y-4">
          {STEPS.map((s, i) => {
            const isDone = i < activeIdx;
            const isActive = i === activeIdx;
            return (
              <li key={s.label} className="flex items-start gap-3">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center">
                  {isDone ? (
                    <CheckCircle2
                      size={18}
                      strokeWidth={2}
                      className="text-[#1e40af]"
                    />
                  ) : isActive ? (
                    <Loader2
                      size={18}
                      strokeWidth={2}
                      className="animate-spin text-[#1e40af]"
                    />
                  ) : (
                    <span className="h-2 w-2 rounded-full bg-outline-variant/40" />
                  )}
                </span>
                <span
                  className={
                    isActive
                      ? "text-sm font-medium text-on-surface"
                      : isDone
                        ? "text-sm text-on-surface-variant"
                        : "text-sm text-on-surface-variant/60"
                  }
                >
                  {s.label}
                </span>
              </li>
            );
          })}
        </ul>

        <div className="mt-6 h-1 w-full overflow-hidden rounded-full bg-surface-container-low">
          <div className="h-full w-1/3 animate-pulse bg-[#1e40af]" />
        </div>

        <p className="mt-4 text-xs text-on-surface-variant">
          The agent is querying Neo4j and embedding pattern descriptions via
          H2OGPTe — typically 3–6 seconds.
        </p>
      </div>
    </div>
  );
}
