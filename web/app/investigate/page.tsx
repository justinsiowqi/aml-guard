"use client";

import { useRef, useState } from "react";
import type { CaseAssessment, InvestigationStep } from "@/lib/types";
import { investigate } from "@/lib/api";
import QuestionBar from "@/components/QuestionBar";
import InvestigationStream from "@/components/InvestigationStream";
import EntityHeader from "@/components/EntityHeader";
import VerdictBanner from "@/components/VerdictBanner";
import FindingsList from "@/components/FindingsList";
import TypologyEvidence from "@/components/TypologyEvidence";
import InvestigationTimeline from "@/components/InvestigationTimeline";
import EntitySubgraph from "@/components/EntitySubgraph";

type Phase = "idle" | "streaming" | "settled";

// Fixed per-step offsets (seconds) anchored to the run's start time.
// Index i = step i's delta from startedAt. Falls back to i*2s beyond the list.
const STEP_OFFSET_SECONDS = [0, 2, 5, 7, 8];
const SETTLE_BUFFER_MS = 500;

function rebaseStepTimestamps(steps: InvestigationStep[], startedAtMs: number): InvestigationStep[] {
  return steps.map((s, i) => {
    const offsetSec = STEP_OFFSET_SECONDS[i] ?? STEP_OFFSET_SECONDS.at(-1)! + (i - STEP_OFFSET_SECONDS.length + 1) * 2;
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
    const rebased = { ...result, investigation_steps: rebaseStepTimestamps(result.investigation_steps, startedAt) };
    setAssessment(rebased);

    // Scroll focus to the subject once it's rendered.
    setTimeout(() => {
      subjectRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 50);

    // Wait for the last agent card to flip done, then reveal the rest.
    const lastTsMs = rebased.investigation_steps.length
      ? new Date(rebased.investigation_steps[rebased.investigation_steps.length - 1].timestamp).getTime()
      : startedAt;
    const revealMs = Math.max(800, lastTsMs - Date.now()) + SETTLE_BUFFER_MS;
    setTimeout(() => setPhase("settled"), revealMs);
  }

  const compact = phase !== "idle";

  return (
    <div className="mx-auto w-full max-w-canvas px-6 py-8 sm:px-10 sm:py-12">
      {compact ? (
        <header className="mb-5">
          <div className="text-[11px] uppercase tracking-[0.18em] text-text-muted">
            AML Guard · Investigation
          </div>
        </header>
      ) : (
        <header className="mb-10">
          <div className="mb-1 text-[11px] uppercase tracking-[0.18em] text-text-muted">
            AML Guard · Investigation
          </div>
          <h1 className="font-display text-4xl leading-tight text-text sm:text-5xl">
            Follow the money. Cite the rule.
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-text-muted">
            An agent traverses the entity graph, runs six anomaly patterns, and matches behaviour
            to MAS Notice 626, FATF, and AUSTRAC typologies — returning a verdict with cited evidence.
          </p>
        </header>
      )}

      <QuestionBar
        onSubmit={handleSubmit}
        disabled={phase === "streaming"}
        currentQuestion={question}
        compact={compact}
      />

      {compact && assessment && (
        <section ref={subjectRef} className="mt-10 scroll-mt-6">
          <EntityHeader subject={assessment.subject} caseId={assessment.case_id} />
        </section>
      )}

      {compact && assessment && (
        <section className="mt-8">
          <InvestigationStream
            steps={assessment.investigation_steps}
            isStreaming={phase === "streaming"}
          />
        </section>
      )}

      {assessment && phase === "settled" && (
        <>
          <section className="mt-6">
            <VerdictBanner
              verdict={assessment.verdict}
              riskScore={assessment.risk_score}
              headline={assessment.headline}
              txVelocity={assessment.tx_velocity}
            />
          </section>

          <section className="mt-10 grid grid-cols-1 gap-8 lg:grid-cols-5">
            <div className="lg:col-span-3">
              <FindingsList findings={assessment.findings} />
            </div>
            <div className="lg:col-span-2">
              <TypologyEvidence chunks={assessment.typology_chunks} />
            </div>
          </section>

          <section className="mt-10 grid grid-cols-1 gap-8 lg:grid-cols-5">
            <div className="lg:col-span-3">
              <InvestigationTimeline steps={assessment.investigation_steps} />
            </div>
            <div className="lg:col-span-2">
              <EntitySubgraph subgraph={assessment.subgraph} />
            </div>
          </section>
        </>
      )}
    </div>
  );
}
