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

export async function mockInvestigateDeep(question: string): Promise<CaseAssessment> {
  // Simulate the longer agent path so the UI's phase animation has time to render.
  await new Promise((r) => setTimeout(r, 6000));
  const payload = pickPreset(question);
  return {
    ...payload,
    question,
    summary:
      "Agent confirmed three high-severity ownership-opacity signals concentrated " +
      "around the subject's registered intermediary. Cross-referenced against MAS " +
      "Notice 626 §6 and FATF Recommendation 24; pattern signature is consistent " +
      "with intermediary-led shell layering.",
    recommended_actions: [
      "Escalate to MLRO for STR pre-filing review within 24 hours.",
      "Freeze new account-opening eligibility pending UBO re-verification.",
      "Request beneficial-ownership documentation directly from the intermediary.",
    ],
  };
}
