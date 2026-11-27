"use client";

import Link from "next/link";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { Loading } from "@/components/ui/Loading";
import { ADVICE_PARTS, type AdviceRef } from "@/lib/api/advice";
import { dimensionHref } from "@/lib/api/insights";
import type { AdviceOut } from "@/lib/api/types";

import {
  ConsultationMessage,
  PartSection,
  RecommendationBody,
  Sentences,
  StillWorking,
  type Ask,
} from "./parts";
import { useAdvice } from "./useAdvice";

/** The AI's advice on one result (AI touchpoints 4, 5, 6 and 8): what it means, a
 * consultation suggestion, recommendations and actions to close the gaps. Every block is
 * marked as the AI's and names its dimension; the method's fixed next steps are shown
 * apart, as written. The only numbers here are the engine's priority ranks. */
export function AdvicePanel({ adviceRef }: { adviceRef: AdviceRef }) {
  const { state, ask, asking, askError, stalled, arrived, checkAgain } = useAdvice(adviceRef);
  const ideaId = adviceRef.kind === "idea" ? adviceRef.ideaId : null;

  return (
    <Card>
      <CardHeader
        title="AI advice"
        description="Written by AI from this result, to help you decide what to do next. It suggests; it never changes a score."
      />
      {/* Tells a screen reader that the advice it was waiting for is now on the page. */}
      <p role="status" aria-live="polite" className="sr-only">
        {arrived ? "The AI has finished. Its advice is on the page." : ""}
      </p>
      <div className="mt-4">
        {state.kind === "loading" && <Loading>Loading the advice...</Loading>}
        {state.kind === "error" && <Alert tone="error">{state.message}</Alert>}
        {state.kind === "ready" && (
          <AdviceBody
            advice={state.advice}
            ideaId={ideaId}
            onAsk={(options) => void ask(options)}
            asking={asking}
            askError={askError}
            stalled={stalled}
            onCheckAgain={checkAgain}
          />
        )}
      </div>
    </Card>
  );
}

function AdviceBody({
  advice,
  ideaId,
  onAsk,
  asking,
  askError,
  stalled,
  onCheckAgain,
}: {
  advice: AdviceOut;
  ideaId: string | null;
  onAsk: Ask;
  asking: boolean;
  askError: string | null;
  stalled: boolean;
  onCheckAgain: () => void;
}) {
  const live = ADVICE_PARTS.filter((part) => advice[part].status !== "off");
  const untouched = live.every((part) => advice[part].status === "none");
  const canRequest = advice.can_request;
  const { interpretation, gap_actions: gaps, recommendations, consultation } = advice;

  if (live.length === 0) {
    return <p className="text-sm text-neutral-600">AI advice is switched off.</p>;
  }
  if (untouched) {
    return (
      <div className="space-y-3">
        {askError && <Alert tone="error">{askError}</Alert>}
        {canRequest ? (
          <>
            <p className="max-w-prose text-sm text-neutral-600">
              Ask the AI to explain this result, recommend what to work on and suggest actions
              for the priorities. It takes about a minute and is saved for everyone who can see
              this result.
            </p>
            <Button busy={asking} onClick={() => onAsk({})}>
              Get AI advice
            </Button>
          </>
        ) : (
          <p className="text-sm text-neutral-600">
            Nobody has asked for advice on this result yet. An owner, admin or team member can
            ask for it.
          </p>
        )}
      </div>
    );
  }

  const section = { canRequest, busy: asking, onAsk, stalled };
  return (
    <div className="space-y-5">
      {askError && <Alert tone="error">{askError}</Alert>}
      {stalled && <StillWorking onCheckAgain={onCheckAgain} />}

      <PartSection
        title="Consultation"
        part="consultation"
        meta={consultation}
        hasContent={consultation.generated_at !== null}
        pendingText="Weighing the gaps..."
        {...section}
      >
        {consultation.suggest ? (
          <ConsultationMessage consultation={consultation} />
        ) : (
          <p className="text-sm text-neutral-700">
            The AI sees no gap wide enough to suggest a consultation.
          </p>
        )}
      </PartSection>

      <PartSection
        title="What this result means"
        part="interpretation"
        meta={interpretation}
        hasContent={interpretation.summary.length > 0}
        pendingText="Putting the result into words..."
        {...section}
      >
        <p className="max-w-prose text-sm text-neutral-800">{interpretation.summary.join(" ")}</p>
        <details className="text-sm">
          <summary className="cursor-pointer font-medium text-primary hover:underline">
            Dimension by dimension
          </summary>
          <ul className="mt-3 divide-y divide-neutral-100">
            {interpretation.dimensions.map((dimension) => (
              <li key={dimension.key} className="space-y-1.5 py-3">
                <Link
                  href={dimensionHref(dimension.key, ideaId)}
                  className="font-medium text-neutral-900 hover:text-primary hover:underline"
                >
                  {dimension.name}
                </Link>
                <p className="text-neutral-700">{dimension.meaning}</p>
                {dimension.strengths.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-neutral-500">Strengths</p>
                    <Sentences items={dimension.strengths} />
                  </div>
                )}
                {dimension.gaps.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-neutral-500">Gaps</p>
                    <Sentences items={dimension.gaps} />
                  </div>
                )}
              </li>
            ))}
          </ul>
        </details>
      </PartSection>

      <PartSection
        title="Recommendations for the priorities"
        part="recommendations"
        meta={recommendations}
        hasContent={recommendations.items.length > 0}
        pendingText="Writing recommendations..."
        mixed
        {...section}
      >
        <ol className="space-y-5">
          {recommendations.items.map((item) => (
            <li key={item.key} className="space-y-2">
              <p className="text-sm font-semibold text-neutral-900">
                <span className="tabular-nums">{item.rank}.</span>{" "}
                <Link href={dimensionHref(item.key, ideaId)} className="hover:text-primary hover:underline">
                  {item.name}
                </Link>
              </p>
              <RecommendationBody item={item} sample={recommendations.sample} />
            </li>
          ))}
        </ol>
      </PartSection>

      <PartSection
        title="Actions to close the gaps"
        part="gap_actions"
        meta={gaps}
        hasContent={gaps.dimensions.length > 0}
        pendingText="Working out actions..."
        {...section}
      >
        <ul className="grid grid-cols-1 gap-x-8 gap-y-4 lg:grid-cols-2">
          {gaps.dimensions.map((dimension) => (
            <li key={dimension.key}>
              <Link
                href={dimensionHref(dimension.key, ideaId)}
                className="text-sm font-medium text-neutral-900 hover:text-primary hover:underline"
              >
                {dimension.name}
              </Link>
              <div className="mt-1">
                <Sentences items={dimension.actions} />
              </div>
            </li>
          ))}
        </ul>
      </PartSection>
    </div>
  );
}
