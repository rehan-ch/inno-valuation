// /api/v1/readiness: the question set and the active organisation's readiness assessments.
import { getJson, patchJson, postJson } from "./client";
import type {
  AssessmentOut,
  AssessmentSummaryOut,
  ConsensusOut,
  ExplanationOut,
  QuestionSetOut,
  ResultOut,
} from "./types";

const BASE = "/readiness";

/** A partial set of answers; null clears an answer. */
export type AnswerChanges = Record<string, number | null>;

export function getQuestionSet(version?: number): Promise<QuestionSetOut> {
  return getJson(`${BASE}/question-set${version ? `?version=${version}` : ""}`);
}

export function listAssessments(init?: RequestInit): Promise<AssessmentSummaryOut[]> {
  return getJson(`${BASE}/assessments`, init);
}

export function startAssessment(): Promise<AssessmentOut> {
  return postJson(`${BASE}/assessments`);
}

export function getAssessment(id: string): Promise<AssessmentOut> {
  return getJson(`${BASE}/assessments/${id}`);
}

export function saveMyAnswers(id: string, answers: AnswerChanges): Promise<AssessmentOut> {
  return patchJson(`${BASE}/assessments/${id}/my-answers`, { answers });
}

export function submitMyAnswers(id: string): Promise<AssessmentOut> {
  return postJson(`${BASE}/assessments/${id}/my-answers/submit`);
}

export function beginConsensus(id: string): Promise<ConsensusOut> {
  return postJson(`${BASE}/assessments/${id}/consensus/begin`);
}

export function getConsensus(id: string): Promise<ConsensusOut> {
  return getJson(`${BASE}/assessments/${id}/consensus`);
}

export function saveConsensus(
  id: string,
  changes: { answers?: AnswerChanges; notes?: Record<string, string | null> },
): Promise<ConsensusOut> {
  return patchJson(`${BASE}/assessments/${id}/consensus`, {
    answers: changes.answers ?? {},
    notes: changes.notes ?? {},
  });
}

export function finaliseAssessment(id: string): Promise<ResultOut> {
  return postJson(`${BASE}/assessments/${id}/finalise`);
}

export function getResult(id: string): Promise<ResultOut> {
  return getJson(`${BASE}/assessments/${id}/result`);
}

/** "What does this mean?": the organisation's saved AI explanation of a question, or a new
 * one on its way (status "pending"; poll getExplanation until "ready" or "failed"). */
export function explainQuestion(questionId: string, version: number): Promise<ExplanationOut> {
  return postJson(`${BASE}/questions/${questionId}/explanation?version=${version}`);
}

export function getExplanation(questionId: string, version: number): Promise<ExplanationOut> {
  return getJson(`${BASE}/questions/${questionId}/explanation?version=${version}`);
}

/** Where an assessment's link should take this person, given its status and their role. */
export function assessmentHref(a: { id: string; status: string }, canManage: boolean): string {
  if (a.status === "final") return `/readiness/${a.id}/result`;
  if (a.status === "consensus" && canManage) return `/readiness/${a.id}/consensus`;
  return `/readiness/${a.id}`;
}
