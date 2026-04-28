"use client";

import { useMemo, useState } from "react";
import {
  BookOpen,
  ChevronLeft,
  ChevronRight,
  Loader2,
  Search,
  X,
} from "lucide-react";
import type { TypologyChunk } from "@/lib/types";
import { searchChunks } from "@/lib/api";

const HIGHLIGHT_KEYWORDS = [
  "linked",
  "structured to avoid",
  "single transaction",
  "enhanced CDD",
  "higher risk",
  "beneficial ownership",
  "misuse of legal persons",
  "politically exposed",
  "wire transfer",
  "correspondent",
];

// Pills carry a short label for the UI and a longer, regulation-flavoured
// query for the embedding model. Single-word queries collapse to noisy
// matches because bge-large has no AML domain knowledge — adding the
// surrounding regulatory phrasing lets the search hit the right paragraph.
const SUGGESTIONS: { label: string; query: string }[] = [
  {
    label: "Structuring",
    query: "transactions linked or structured to avoid reporting thresholds",
  },
  {
    label: "Beneficial ownership",
    query: "identify the natural persons who ultimately own or control a customer",
  },
  {
    label: "High-risk jurisdictions",
    query: "enhanced customer due diligence higher risk countries inadequate AML/CFT",
  },
  {
    label: "PEPs",
    query: "politically exposed persons immediate family members close associates",
  },
  {
    label: "Wire transfers",
    query: "wire transfer originator and beneficiary information",
  },
];

function highlight(text: string): React.ReactNode[] {
  let result: React.ReactNode[] = [text];
  HIGHLIGHT_KEYWORDS.forEach((kw, idx) => {
    const next: React.ReactNode[] = [];
    result.forEach((part) => {
      if (typeof part !== "string") {
        next.push(part);
        return;
      }
      const segments = part.split(new RegExp(`(${kw})`, "i"));
      segments.forEach((seg, i) => {
        if (i % 2 === 1) {
          next.push(
            <span
              key={`h-${idx}-${i}-${seg}`}
              className="border-b border-secondary bg-secondary-fixed/50 px-1 font-sans font-semibold not-italic"
            >
              {seg}
            </span>,
          );
        } else if (seg) {
          next.push(seg);
        }
      });
    });
    result = next;
  });
  return result;
}

export default function TypologyEvidence({ chunks }: { chunks: TypologyChunk[] }) {
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<TypologyChunk[] | null>(null);
  const [activeQuery, setActiveQuery] = useState<string>("");
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [idx, setIdx] = useState(0);

  const inSearchMode = searchResults !== null;
  const displayed = inSearchMode ? searchResults : chunks;

  const sorted = useMemo(
    () => [...displayed].sort((a, b) => b.similarity_score - a.similarity_score),
    [displayed],
  );
  const active = sorted[idx];

  async function runSearch(q: string) {
    const trimmed = q.trim();
    if (!trimmed) return;
    setQuery(trimmed);
    setIsSearching(true);
    setError(null);
    try {
      const results = await searchChunks(trimmed, 6);
      setSearchResults(results);
      setActiveQuery(trimmed);
      setIdx(0);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Search failed");
    } finally {
      setIsSearching(false);
    }
  }

  function clearSearch() {
    setSearchResults(null);
    setActiveQuery("");
    setQuery("");
    setIdx(0);
    setError(null);
  }

  const prev = () => setIdx((i) => Math.max(0, i - 1));
  const next = () => setIdx((i) => Math.min(sorted.length - 1, i + 1));

  return (
    <div className="flex h-full flex-col rounded border border-outline-variant/30 bg-[#e4e5e6] p-5">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BookOpen size={16} strokeWidth={1.75} className="text-tertiary-container" />
          <span className="text-xs font-bold uppercase tracking-wider text-on-surface">
            Citation Viewer
          </span>
        </div>
        <span className="rounded border border-[#a8aaac]/40 bg-[#c4c6c8] px-2 py-1 font-mono text-[10px] font-bold tracking-wider text-on-surface">
          MAS-626
        </span>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          runSearch(query);
        }}
        className="mb-2 flex items-center gap-1 rounded border border-outline-variant/40 bg-white px-2 py-1.5 shadow-sm focus-within:border-primary/60"
      >
        <Search size={14} strokeWidth={1.75} className="text-on-surface-variant" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search MAS-626…"
          className="flex-1 bg-transparent px-1 text-[13px] text-on-surface outline-none placeholder:text-on-surface-variant/60"
          disabled={isSearching}
        />
        {inSearchMode && (
          <button
            type="button"
            onClick={clearSearch}
            aria-label="Clear search"
            className="rounded p-0.5 text-on-surface-variant hover:bg-surface-container-low/60"
          >
            <X size={14} strokeWidth={1.75} />
          </button>
        )}
        <button
          type="submit"
          disabled={isSearching || !query.trim()}
          className="rounded bg-[#1e40af] px-2.5 py-1 text-[11px] font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40"
        >
          {isSearching ? <Loader2 size={12} className="animate-spin" /> : "Go"}
        </button>
      </form>

      <div className="mb-3 flex flex-wrap gap-1.5">
        {SUGGESTIONS.map((s) => (
          <button
            key={s.label}
            type="button"
            onClick={() => runSearch(s.query)}
            disabled={isSearching}
            title={s.query}
            className="rounded-full border border-outline-variant/40 bg-white/60 px-2 py-0.5 text-[10px] text-on-surface-variant transition-colors hover:border-primary/40 hover:text-on-surface disabled:opacity-50"
          >
            {s.label}
          </button>
        ))}
      </div>

      <div className="mb-3 text-[10px] font-medium uppercase tracking-wider text-on-surface-variant">
        {inSearchMode ? (
          <>
            Search · <span className="font-semibold text-on-surface">{activeQuery}</span> ·{" "}
            {sorted.length} {sorted.length === 1 ? "match" : "matches"}
          </>
        ) : (
          <>Case context · {sorted.length} cited paragraphs</>
        )}
      </div>

      {error && (
        <div className="mb-3 rounded border border-[#ba1a1a]/40 bg-[#ffdad6]/40 px-2 py-1.5 text-[11px] text-[#7a1d1d]">
          {error}
        </div>
      )}

      {!active ? (
        <div className="flex flex-1 items-center justify-center rounded border border-dashed border-outline-variant/40 bg-white/40 p-6 text-center text-xs text-on-surface-variant">
          {inSearchMode
            ? "No paragraphs matched. Try a broader query."
            : "No regulatory citations attached to this case."}
        </div>
      ) : (
        <>
          <div className="mb-4">
            <div className="mb-1 flex items-center justify-between">
              <div className="text-[10px] font-bold uppercase tracking-wider text-on-surface-variant">
                Source Directive
              </div>
              <span className="rounded border border-[#a8aaac]/40 bg-[#c4c6c8] px-2 py-0.5 font-mono text-[10px] font-bold tracking-wider text-on-surface">
                REF: {active.id.toUpperCase()}
              </span>
            </div>
            <div className="text-sm font-medium text-on-surface">
              {active.source} · {active.section}
            </div>
            <div className="mt-0.5 text-xs text-on-surface-variant">{active.title}</div>
          </div>

          <div className="relative flex-1 overflow-hidden rounded border border-outline-variant/20 bg-white shadow-sm">
            <div className="h-1 w-full bg-tertiary-container" />
            <div className="relative p-5">
              <div className="absolute left-0 top-0 h-full w-1 bg-tertiary-container" />
              <p className="font-serif text-sm italic leading-relaxed text-on-surface">
                {highlight(active.text)}
              </p>
            </div>
            <div className="h-px w-full bg-outline-variant/30" />
            <div className="flex items-center justify-between px-5 py-2 font-mono text-[10px] text-on-surface-variant">
              <span>{active.source}</span>
              <span>{active.section}</span>
            </div>
          </div>

          {sorted.length > 1 && (
            <div className="mt-3 flex items-center justify-between">
              <button
                type="button"
                onClick={prev}
                disabled={idx === 0}
                className="flex items-center gap-1 text-xs text-on-surface-variant transition-colors hover:text-on-surface disabled:opacity-30"
              >
                <ChevronLeft size={14} strokeWidth={1.75} />
                Prev
              </button>
              <span className="font-mono text-[11px] text-on-surface-variant">
                {idx + 1} / {sorted.length} · sim {Math.round(active.similarity_score * 100)}%
              </span>
              <button
                type="button"
                onClick={next}
                disabled={idx === sorted.length - 1}
                className="flex items-center gap-1 text-xs text-on-surface-variant transition-colors hover:text-on-surface disabled:opacity-30"
              >
                Next
                <ChevronRight size={14} strokeWidth={1.75} />
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
