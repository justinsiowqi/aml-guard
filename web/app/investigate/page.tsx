"use client";

import { useRef, useState } from "react";
import type { CaseAssessment, InvestigationStep } from "@/lib/types";
import { investigate } from "@/lib/api";
import QuestionBar from "@/components/QuestionBar";
import TopHeader from "@/components/TopHeader";
import EntityHeader from "@/components/EntityHeader";
import InvestigationStream from "@/components/InvestigationStream";
import VerdictBanner from "@/components/VerdictBanner";
import FindingsList from "@/components/FindingsList";
import TypologyEvidence from "@/components/TypologyEvidence";
import EntitySubgraph from "@/components/EntitySubgraph";

type Phase = "idle" | "streaming" | "settled";

const STEP_OFFSET_SECONDS = [0, 2, 5, 7, 8];
const SETTLE_BUFFER_MS = 500;

function rebaseStepTimestamps(steps: InvestigationStep[], startedAtMs: number): InvestigationStep[] {
  return steps.map((s, i) => {
    const offsetSec =
      STEP_OFFSET_SECONDS[i] ??
      STEP_OFFSET_SECONDS.at(-1)! + (i - STEP_OFFSET_SECONDS.length + 1) * 2;
    return { ...s, timestamp: new Date(startedAtMs + offsetSec * 1000).toISOString() };
  });
}

export default function InvestigatePage() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [assessment, setAssessment] = useState<CaseAssessment | null>(null);
  const [question, setQuestion] = useState<string>("");
  const subjectRef = useRef<HTMLDivElement | null>(null);

  async function handleSubmit(q: string) {
    setQuestion(q);
    setPhase("streaming");
    setAssessment(null);
    const startedAt = Date.now();
    const result = await investigate(q);
    const rebased = {
      ...result,
      investigation_steps: rebaseStepTimestamps(result.investigation_steps, startedAt),
    };
    setAssessment(rebased);

    setTimeout(() => {
      subjectRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 50);

    const lastTsMs = rebased.investigation_steps.length
      ? new Date(rebased.investigation_steps[rebased.investigation_steps.length - 1].timestamp).getTime()
      : startedAt;
    const revealMs = Math.max(800, lastTsMs - Date.now()) + SETTLE_BUFFER_MS;
    setTimeout(() => setPhase("settled"), revealMs);
  }

  return (
    <>
      <TopHeader caseId={assessment?.case_id} jurisdiction={assessment?.subject.jurisdiction} />

      <div className="flex-1 overflow-auto p-6">
        {phase === "idle" && (
          <div className="mx-auto max-w-3xl py-12">
            <header className="mb-8">
              <div className="mb-1 text-[11px] uppercase tracking-[0.18em] text-on-surface-variant">
                AML Guard · Investigation
              </div>
              <h1 className="text-4xl font-black leading-tight tracking-tight text-on-surface sm:text-5xl">
                Follow the money. Cite the rule.
              </h1>
              <p className="mt-2 max-w-2xl text-sm text-on-surface-variant">
                An agent traverses the entity graph, runs six anomaly patterns, and matches
                behaviour to MAS Notice 626, FATF, and AUSTRAC typologies — returning a verdict
                with cited evidence.
              </p>
            </header>

            <QuestionBar
              onSubmit={handleSubmit}
              disabled={false}
              currentQuestion={question}
            />
          </div>
        )}

        {phase !== "idle" && assessment && (
          <div ref={subjectRef}>
            <EntityHeader subject={assessment.subject} phase={phase} />

            <div className="mb-6 grid grid-cols-12 gap-6">
              <div className="col-span-12 lg:col-span-8">
                {phase === "settled" ? (
                  <VerdictBanner
                    verdict={assessment.verdict}
                    riskScore={assessment.risk_score}
                    headline={assessment.headline}
                    txVelocity={assessment.tx_velocity}
                  />
                ) : (
                  <div className="flex h-full min-h-[220px] items-center justify-center rounded border border-dashed border-outline-variant/40 bg-surface-container-lowest p-8 text-sm text-on-surface-variant">
                    Verdict pending — agent is gathering evidence…
                  </div>
                )}
              </div>
              <div className="col-span-12 lg:col-span-4">
                <InvestigationStream
                  steps={assessment.investigation_steps}
                  isStreaming={phase === "streaming"}
                />
              </div>
            </div>

            {phase === "settled" && (
              <>
                <div className="mb-6 grid grid-cols-12 gap-6">
                  <div className="col-span-12 lg:col-span-8">
                    <FindingsList findings={assessment.findings} />
                  </div>
                  <div className="col-span-12 lg:col-span-4">
                    <TypologyEvidence chunks={assessment.typology_chunks} />
                  </div>
                </div>

                <EntitySubgraph subgraph={assessment.subgraph} />
              </>
            )}
          </div>
        )}
      </div>
    </>
  );
}
