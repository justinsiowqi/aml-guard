"use client";

import { useState } from "react";
import { ArrowRight } from "lucide-react";

const PRESETS = [
  "Who really owns Nielsen Enterprises Limited?",
  "Which customers are routing money through Swiss banks?",
  "Are small repeated payments being used to hide a large transfer through Mossack Fonseca?",
];

export default function QuestionBar({
  onSubmit,
  disabled,
  currentQuestion,
}: {
  onSubmit: (q: string) => void;
  disabled: boolean;
  currentQuestion: string;
}) {
  const [value, setValue] = useState(currentQuestion);

  function submit(q: string) {
    const trimmed = q.trim();
    if (!trimmed || disabled) return;
    setValue(trimmed);
    onSubmit(trimmed);
  }

  return (
    <div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(value);
        }}
        className="flex items-center gap-2 rounded border border-outline-variant/30 bg-surface-container-lowest px-3 py-2 shadow-sm focus-within:border-primary/60"
      >
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Ask the agent to investigate an entity…"
          className="flex-1 bg-transparent px-1 py-2 text-[15px] text-on-surface outline-none placeholder:text-on-surface-variant/60"
          disabled={disabled}
        />
        <button
          type="submit"
          disabled={disabled || !value.trim()}
          className="flex h-9 items-center gap-2 rounded bg-[#1e40af] px-4 text-[13px] font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40"
        >
          Investigate
          <ArrowRight size={14} strokeWidth={2} />
        </button>
      </form>

      <div className="mt-3 flex flex-wrap gap-2">
        {PRESETS.map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => submit(p)}
            disabled={disabled}
            className="rounded-full border border-outline-variant/30 bg-surface-container-lowest px-3 py-1.5 text-[12px] text-on-surface-variant transition-colors hover:border-primary/40 hover:text-on-surface disabled:opacity-50"
          >
            {p}
          </button>
        ))}
      </div>
    </div>
  );
}
