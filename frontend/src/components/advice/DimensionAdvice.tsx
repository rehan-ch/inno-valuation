"use client";

import Link from "next/link";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Loading } from "@/components/ui/Loading";
import { ADVICE_PARTS, type AdviceRef } from "@/lib/api/advice";

import { ProposedByAi, RecommendationBody, Sentences } from "./parts";
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
  const { state, ask, asking, askError } = useAdvice(adviceRef);

  return (
    <section aria-label={heading} className="border-t border-neutral-200 pt-4 first:border-t-0 first:pt-0">
      <h3 className="text-sm font-semibold text-neutral-900">{heading}</h3>
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
            const sample =
              advice.interpretation.sample || advice.gap_actions.sample || advice.recommendations.sample;
            const nothing = !meaning && !actions && !recommendation;
            const failed = live.some((part) => advice[part].status === "failed");
            const asked = live.some((part) => advice[part].status !== "none");
            if (live.length === 0) {
              return <p className="text-sm text-neutral-600">AI advice is switched off.</p>;
            }
            return (
              <>
                {pending && <Loading>The AI is writing its advice...</Loading>}
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
                    <ProposedByAi sample={sample} />
                    {meaning && (
                      <div className="space-y-1.5">
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
                        <p className="text-xs font-medium text-neutral-500">Actions to close the gap</p>
                        <div className="mt-1">
                          <Sentences items={actions.actions} />
                        </div>
                      </div>
                    )}
                    {recommendation && <RecommendationBody item={recommendation} />}
                    {reason && advice.consultation.suggest && (
                      <p className="text-sm text-neutral-700">
                        <span className="font-medium text-neutral-900">
                          The AI suggests a consultation:{" "}
                        </span>
                        {reason.reason}
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
                        : "Written by AI. It can be wrong, so use your own judgement. "}
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
