import type { CaseAssessment, TypologyChunk } from "./types";
import { mockInvestigate, mockInvestigateDeep } from "./mock-adapter";

export async function investigate(question: string): Promise<CaseAssessment> {
  const base = process.env.NEXT_PUBLIC_API_BASE;
  if (!base) return mockInvestigate(question);
  const res = await fetch(`${base}/api/investigate`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) {
    throw new Error(`investigate failed: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as CaseAssessment;
}

export async function investigateDeep(question: string): Promise<CaseAssessment> {
  const base = process.env.NEXT_PUBLIC_API_BASE;
  if (!base) return mockInvestigateDeep(question);
  const res = await fetch(`${base}/api/investigate/deep`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) {
    throw new Error(`investigateDeep failed: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as CaseAssessment;
}

export async function searchChunks(
  query: string,
  topK = 6,
): Promise<TypologyChunk[]> {
  const base = process.env.NEXT_PUBLIC_API_BASE;
  if (!base) return [];
  const res = await fetch(`${base}/api/chunks`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ query_text: query, top_k: topK }),
  });
  if (!res.ok) {
    throw new Error(`searchChunks failed: ${res.status} ${res.statusText}`);
  }
  const payload = (await res.json()) as { chunks: TypologyChunk[] };
  return payload.chunks ?? [];
}
