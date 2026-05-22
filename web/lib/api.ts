import type { CaseAssessment, DeepStatus, TypologyChunk } from "./types";
import {
  mockCancelDeep,
  mockGetDeepStatus,
  mockInvestigate,
  mockStartDeep,
} from "./mock-adapter";

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

export interface DeepStartResponse {
  job_id: string;
  case: CaseAssessment;
}

export async function startDeepAnalysis(question: string): Promise<DeepStartResponse> {
  const base = process.env.NEXT_PUBLIC_API_BASE;
  if (!base) return mockStartDeep(question);
  const res = await fetch(`${base}/api/investigate/deep`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) {
    throw new Error(`startDeepAnalysis failed: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as DeepStartResponse;
}

export async function getDeepStatus(jobId: string): Promise<DeepStatus> {
  const base = process.env.NEXT_PUBLIC_API_BASE;
  if (!base) return mockGetDeepStatus(jobId);
  const res = await fetch(`${base}/api/investigate/deep/status/${jobId}`);
  if (!res.ok) {
    throw new Error(`getDeepStatus failed: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as DeepStatus;
}

export async function cancelDeepAnalysis(jobId: string): Promise<void> {
  const base = process.env.NEXT_PUBLIC_API_BASE;
  if (!base) return mockCancelDeep(jobId);
  await fetch(`${base}/api/investigate/deep/cancel/${jobId}`, { method: "POST" });
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
