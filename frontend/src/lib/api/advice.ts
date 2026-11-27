// AI advice on one result (Phase 6): a final readiness result, or an idea's confirmed
// scores. Asking returns at once with parts "pending"; poll getAdvice until none is.
import { getJson, postJson } from "./client";
import type { AdviceOut, AdvicePartName } from "./types";

/** Which result the advice is about. The two scores never share advice. */
export type AdviceRef =
  | { kind: "readiness"; assessmentId: string }
  | { kind: "idea"; ideaId: string; assessmentId: string };

function path(ref: AdviceRef): string {
  return ref.kind === "readiness"
    ? `/readiness/assessments/${ref.assessmentId}/advice`
    : `/ideas/${ref.ideaId}/assessments/${ref.assessmentId}/advice`;
}

export function getAdvice(ref: AdviceRef): Promise<AdviceOut> {
  return getJson(path(ref));
}

/** Ask for every part that has no answer yet, or only `parts`. `regenerate` asks again
 * for parts that already have one. */
export function requestAdvice(
  ref: AdviceRef,
  options: { parts?: AdvicePartName[]; regenerate?: boolean } = {},
): Promise<AdviceOut> {
  return postJson(path(ref), {
    parts: options.parts ?? null,
    regenerate: options.regenerate ?? false,
  });
}

export const ADVICE_PARTS: AdvicePartName[] = [
  "interpretation",
  "gap_actions",
  "recommendations",
  "consultation",
];
