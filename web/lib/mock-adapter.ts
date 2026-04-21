import type { CaseAssessment } from "./types";
import nielsen from "@/mocks/nielsen-enterprises.json";

const PRESET_ANSWERS: Record<string, CaseAssessment> = {
  nielsen: nielsen as CaseAssessment,
};

function pickPreset(question: string): CaseAssessment {
  const q = question.toLowerCase();
  // Everything currently routes to the single scripted case.
  if (q.includes("nescoll") || q.includes("hangon") || q.includes("nielsen") || q.includes("mossack") || q.includes("jonathan") || q.includes("bsi")) {
    return PRESET_ANSWERS.nielsen;
  }
  return PRESET_ANSWERS.nielsen;
}

export async function mockInvestigate(question: string): Promise<CaseAssessment> {
  await new Promise((r) => setTimeout(r, 400));
  const payload = pickPreset(question);
  return { ...payload, question };
}
