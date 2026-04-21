"use client";

import { useState } from "react";
import { ArrowRight, Pencil } from "lucide-react";

const PRESETS = [
  "Investigate Nielsen Enterprises Limited for beneficial owner opacity",
  "Trace Jonathan Lim Wei Ming through the BSI Bank Geneva corridor",
  "Any structuring behaviour linked to Mossack Fonseca intermediaries?",
];

export default function QuestionBar({
  onSubmit,
  disabled,
  currentQuestion,
  compact = false,
}: {
  onSubmit: (q: string) => void;
  disabled: boolean;
  currentQuestion: string;
  compact?: boolean;
}) {
  const [value, setValue] = useState(currentQuestion);
  const [editing, setEditing] = useState(false);

  function submit(q: string) {
    const trimmed = q.trim();
    if (!trimmed || disabled) return;
    setValue(trimmed);
    setEditing(false);
    onSubmit(trimmed);
  }

  if (compact && !editing) {
    return (
      <button
        type="button"
        onClick={() => setEditing(true)}
        disabled={disabled}
        className="group flex w-full items-center gap-3 rounded-md border border-border bg-surface px-3 py-2 text-left shadow-sm transition-colors hover:border-text/30 disabled:opacity-60"
      >
        <span className="text-[10.5px] uppercase tracking-[0.16em] text-text-muted">Query</span>
        <span className="min-w-0 flex-1 truncate text-[13px] text-text">{currentQuestion || value}</span>
        <span className="flex items-center gap-1 text-[11px] text-text-muted transition-colors group-hover:text-text">
          <Pencil size={12} strokeWidth={1.75} />
          edit
        </span>
      </button>
    );
  }

  return (
    <div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(value);
        }}
        className="flex items-center gap-2 rounded-md border border-border bg-surface px-3 py-2 shadow-sm focus-within:border-text/40"
      >
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Ask the agent to investigate an entity…"
          className="flex-1 bg-transparent px-1 py-2 text-[15px] outline-none placeholder:text-text-muted"
          disabled={disabled}
          autoFocus={compact}
        />
        {compact && (
          <button
            type="button"
            onClick={() => {
              setValue(currentQuestion);
              setEditing(false);
            }}
            className="text-[12px] text-text-muted transition-colors hover:text-text"
          >
            cancel
          </button>
        )}
        <button
          type="submit"
          disabled={disabled || !value.trim()}
          className="flex h-9 items-center gap-2 rounded-md bg-text px-4 text-[13px] font-medium text-surface transition-opacity hover:opacity-90 disabled:opacity-40"
        >
          {compact ? "Re-run" : "Investigate"}
          <ArrowRight size={14} strokeWidth={2} />
        </button>
      </form>

      {!compact && (
        <div className="mt-3 flex flex-wrap gap-2">
          {PRESETS.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => submit(p)}
              disabled={disabled}
              className="rounded-full border border-border bg-surface px-3 py-1.5 text-[12px] text-text-muted transition-colors hover:border-text/30 hover:text-text disabled:opacity-50"
            >
              {p}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
