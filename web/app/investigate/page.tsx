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

const PLACEHOLDER_STEP_TEMPLATE: Omit<InvestigationStep, "timestamp">[] = [
  {
    tool: "traverse_entity_network",
    summary: "Pulling 2-hop entity subgraph from the graph…",
  },
  {
    tool: "detect_graph_anomalies",
    summary: "Running 6 anomaly patterns against Layer 1…",
  },
  {
    tool: "retrieve_typology_chunks",
    summary: "Retrieving regulatory citations per fired pattern…",
  },
];

function rebaseStepTimestamps(steps: InvestigationStep[], startedAtMs: number): InvestigationStep[] {
  return steps.map((s, i) => {
    const offsetSec =
      STEP_OFFSET_SECONDS[i] ??
      STEP_OFFSET_SECONDS.at(-1)! + (i - STEP_OFFSET_SECONDS.length + 1) * 2;
    return { ...s, timestamp: new Date(startedAtMs + offsetSec * 1000).toISOString() };
  });
}

function buildPlaceholderSteps(startedAtMs: number): InvestigationStep[] {
  return PLACEHOLDER_STEP_TEMPLATE.map((s, i) => ({
    ...s,
    timestamp: new Date(startedAtMs + STEP_OFFSET_SECONDS[i] * 1000).toISOString(),
  }));
}

export default function InvestigatePage() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [assessment, setAssessment] = useState<CaseAssessment | null>(null);
  const [question, setQuestion] = useState<string>("");
  const [startedAt, setStartedAt] = useState<number>(0);
  const [placeholderSteps, setPlaceholderSteps] = useState<InvestigationStep[]>([]);
  const [handedOff, setHandedOff] = useState(false);
  const [sarFiled, setSarFiled] = useState(false);
  const subjectRef = useRef<HTMLDivElement | null>(null);

  async function handleSubmit(q: string) {
    setQuestion(q);
    setPhase("streaming");
    setAssessment(null);
    setHandedOff(false);
    setSarFiled(false);
    const startedAt = Date.now();
    setStartedAt(startedAt);
    setPlaceholderSteps(buildPlaceholderSteps(startedAt));
    setTimeout(() => {
      subjectRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 50);
    const result = await investigate(q);
    const rebased = {
      ...result,
      investigation_steps: rebaseStepTimestamps(result.investigation_steps, startedAt),
    };
    setAssessment(rebased);

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
                behaviour to MAS Notice 626 and FATF typologies — returning a verdict
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

        {phase !== "idle" && (
          <div ref={subjectRef}>
            {assessment ? (
              <EntityHeader
                subject={assessment.subject}
                caseId={assessment.case_id}
                phase={phase}
                handedOff={handedOff}
                sarFiled={sarFiled}
              />
            ) : (
              <div className="mb-8">
                <div className="mb-1 text-[11px] uppercase tracking-[0.18em] text-on-surface-variant">
                  AML Guard · Investigation in progress
                </div>
                <h1 className="text-2xl font-bold leading-tight tracking-tight text-on-surface">
                  {question}
                </h1>
              </div>
            )}

            <div className="mb-6 grid grid-cols-12 gap-6">
              <div className="col-span-12 lg:col-span-8">
                {phase === "settled" && assessment ? (
                  <VerdictBanner
                    verdict={assessment.verdict}
                    riskScore={assessment.risk_score}
                    headline={assessment.headline}
                    txVelocity={assessment.tx_velocity}
                    caseId={assessment.case_id}
                    handedOff={handedOff}
                    onHandoff={() => setHandedOff(true)}
                    onSarFiled={() => setSarFiled(true)}
                  />
                ) : (
                  <div className="flex h-full min-h-[220px] items-center justify-center rounded border border-dashed border-outline-variant/40 bg-surface-container-lowest p-8 text-sm text-on-surface-variant">
                    Verdict pending — agent is gathering evidence…
                  </div>
                )}
              </div>
              <div className="col-span-12 lg:col-span-4">
                <InvestigationStream
                  key={startedAt}
                  steps={assessment?.investigation_steps ?? placeholderSteps}
                  isStreaming={phase === "streaming"}
                />
              </div>
            </div>

            {phase === "settled" && assessment && (
              <>
                <div className="mb-6 grid grid-cols-12 items-start gap-6">
                  <div className="col-span-12 lg:col-span-8">
                    <FindingsList
                      findings={assessment.findings}
                      chunks={assessment.typology_chunks}
                    />
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
