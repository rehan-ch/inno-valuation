"use client";

import Link from "next/link";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Loading } from "@/components/ui/Loading";
import { ADVICE_PARTS, type AdviceRef } from "@/lib/api/advice";

import { OUTDATED_TEXT, ProposedByAi, RecommendationBody, Sentences, StillWorking } from "./parts";
import { useAdvice } from "./useAdvice";

/** The AI's advice about one dimension of one result, for the dimension page: what its
 * score means, and, when the dimension is a priority or has a target above its score, the
 * recommendation and the actions. The full advice lives on the result page. */
export function DimensionAdvice({
  adviceRef,
  dimensionKey,
  heading,
  resultHref,
}: {
  adviceRef: AdviceRef;
  dimensionKey: string;
  heading: string;
  resultHref: string;
}) {
  const { state, ask, asking, askError, stalled, arrived, checkAgain } = useAdvice(adviceRef);

  return (
    <section aria-label={heading} className="border-t border-neutral-200 pt-4 first:border-t-0 first:pt-0">
      <h3 className="text-sm font-semibold text-neutral-900">{heading}</h3>
      {/* Tells a screen reader that the advice it was waiting for is now on the page. */}
      <p role="status" aria-live="polite" className="sr-only">
        {arrived ? "The AI has finished. Its advice is on the page." : ""}
      </p>
      <div className="mt-2 space-y-3">
        {state.kind === "loading" && <Loading>Loading the advice...</Loading>}
        {state.kind === "error" && <Alert tone="error">{state.message}</Alert>}
        {askError && <Alert tone="error">{askError}</Alert>}
        {state.kind === "ready" &&
          (() => {
            const { advice } = state;
            const live = ADVICE_PARTS.filter((part) => advice[part].status !== "off");
            const pending = live.some((part) => advice[part].status === "pending");
            const meaning = advice.interpretation.dimensions.find((d) => d.key === dimensionKey);
            const actions = advice.gap_actions.dimensions.find((d) => d.key === dimensionKey);
            const recommendation = advice.recommendations.items.find((i) => i.key === dimensionKey);
            const reason = advice.consultation.reasons.find((r) => r.key === dimensionKey);
            const suggestion = reason && advice.consultation.suggest ? reason : undefined;
            // Only the parts with text on this page count: the others are not shown here.
            const shown = [
              ...(meaning ? [advice.interpretation] : []),
              ...(actions ? [advice.gap_actions] : []),
              ...(recommendation ? [advice.recommendations] : []),
              ...(suggestion ? [advice.consultation] : []),
            ];
            const sample = shown.some((part) => part.sample);
            const outdated = shown.some((part) => part.outdated);
            const nothing = !meaning && !actions && !recommendation;
            const failed = live.some((part) => advice[part].status === "failed");
            const asked = live.some((part) => advice[part].status !== "none");
            if (live.length === 0) {
              return <p className="text-sm text-neutral-600">AI advice is switched off.</p>;
            }
            return (
              <>
                {pending && !stalled && <Loading>The AI is writing its advice...</Loading>}
                {pending && stalled && <StillWorking onCheckAgain={checkAgain} />}
                {!asked &&
                  (advice.can_request ? (
                    <>
                      <p className="text-sm text-neutral-600">
                        No advice has been asked for on this result yet. It takes about a minute.
                      </p>
                      <Button variant="secondary" size="sm" busy={asking} onClick={() => void ask({})}>
                        Get AI advice
                      </Button>
                    </>
                  ) : (
                    <p className="text-sm text-neutral-600">
                      Nobody has asked for advice on this result yet.
                    </p>
                  ))}
                {asked && nothing && !pending && failed && (
                  <Alert tone="error">
                    The AI could not write its advice right now.{" "}
                    <Link href={resultHref} className="font-medium underline">
                      Open the result to try again
                    </Link>
                  </Alert>
                )}
                {asked && nothing && !pending && !failed && (
                  <p className="text-sm text-neutral-600">
                    There is no advice about this dimension yet.{" "}
                    <Link href={resultHref} className="font-medium text-primary hover:underline">
                      See the full advice
                    </Link>
                  </p>
                )}
                {!nothing && (
                  <div className="space-y-4">
                    {outdated && !pending && (
                      <Alert tone="info">
                        {OUTDATED_TEXT}{" "}
                        <Link href={resultHref} className="font-medium text-primary hover:underline">
                          {advice.can_request ? "Open the result to ask again" : "Open the result"}
                        </Link>
                      </Alert>
                    )}
                    {meaning && (
                      <div className="space-y-1.5">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-xs font-medium text-neutral-500">What the result means here</p>
                          <ProposedByAi sample={advice.interpretation.sample} />
                        </div>
                        <p className="text-sm text-neutral-800">{meaning.meaning}</p>
                        {meaning.strengths.length > 0 && (
                          <div>
                            <p className="text-xs font-medium text-neutral-500">Strengths</p>
                            <Sentences items={meaning.strengths} />
                          </div>
                        )}
                        {meaning.gaps.length > 0 && (
                          <div>
                            <p className="text-xs font-medium text-neutral-500">Gaps</p>
                            <Sentences items={meaning.gaps} />
                          </div>
                        )}
                      </div>
                    )}
                    {actions && (
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-xs font-medium text-neutral-500">Actions to close the gap</p>
                          <ProposedByAi sample={advice.gap_actions.sample} />
                        </div>
                        <div className="mt-1">
                          <Sentences items={actions.actions} />
                        </div>
                      </div>
                    )}
                    {recommendation && (
                      <RecommendationBody item={recommendation} sample={advice.recommendations.sample} />
                    )}
                    {suggestion && (
                      <p className="text-sm text-neutral-700">
                        <span className="font-medium text-neutral-900">
                          The AI suggests a consultation:{" "}
                        </span>
                        {suggestion.reason}
                      </p>
                    )}
                    {!actions && !recommendation && (
                      <p className="text-xs text-neutral-500">
                        This dimension is not among the priorities and has no target above its
                        score, so the AI wrote no actions for it.
                      </p>
                    )}
                    <p className="text-xs text-neutral-500">
                      {sample
                        ? "Sample text: the AI is not connected yet. "
                        : 'The text marked "Proposed by AI" was written by AI. It can be wrong, so use your own judgement. '}
                      <Link href={resultHref} className="font-medium text-primary hover:underline">
                        Full advice, and ask again
                      </Link>
                    </p>
                  </div>
                )}
              </>
            );
          })()}
      </div>
    </section>
  );
}
