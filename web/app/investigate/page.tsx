"use client";

import { useState } from "react";
import type { CaseAssessment } from "@/lib/types";
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

export default function InvestigatePage() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [assessment, setAssessment] = useState<CaseAssessment | null>(null);
  const [question, setQuestion] = useState<string>("");

  async function handleSubmit(q: string) {
    setQuestion(q);
    setPhase("streaming");
    setAssessment(null);
    const result = await investigate(q);
    setAssessment(result);
    // Let the step stagger play (5 × 450ms), then settle for the rest of the UI.
    const stepCount = result.investigation_steps.length;
    const revealMs = stepCount * 450 + 300;
    setTimeout(() => setPhase("settled"), revealMs);
  }

  return (
    <div className="mx-auto w-full max-w-canvas px-6 py-8 sm:px-10 sm:py-12">
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

      <QuestionBar onSubmit={handleSubmit} disabled={phase === "streaming"} currentQuestion={question} />

      {phase !== "idle" && (
        <section className="mt-10">
          <InvestigationStream
            steps={assessment?.investigation_steps ?? []}
            isStreaming={phase === "streaming"}
          />
        </section>
      )}

      {assessment && phase === "settled" && (
        <>
          <section className="mt-12">
            <EntityHeader subject={assessment.subject} caseId={assessment.case_id} />
          </section>

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

          <footer className="mt-16 border-t border-border pt-6 text-[11px] uppercase tracking-[0.16em] text-text-muted">
            Case {assessment.case_id} · Agent AMLAgent / claude-sonnet-4-6 · Written to Layer 3
          </footer>
        </>
      )}
    </div>
  );
}
