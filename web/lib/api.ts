import type { CaseAssessment } from "./types";
import { mockInvestigate } from "./mock-adapter";

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
