// /api/v1/ideas: the active organisation's ideas and their IQ assessments.
import { getJson, patchJson, postJson } from "./client";
import type {
  IdeaCreateIn,
  IdeaOut,
  IdeaSummaryOut,
  IdeaUpdateIn,
  IqAssessmentOut,
  ReviewIn,
} from "./types";

const BASE = "/ideas";

export function listIdeas(includeArchived = false, init?: RequestInit): Promise<IdeaSummaryOut[]> {
  return getJson(`${BASE}${includeArchived ? "?include_archived=true" : ""}`, init);
}

export function createIdea(input: IdeaCreateIn): Promise<IdeaOut> {
  return postJson(BASE, input);
}

export function getIdea(id: string): Promise<IdeaOut> {
  return getJson(`${BASE}/${id}`);
}

export function updateIdea(id: string, input: IdeaUpdateIn): Promise<IdeaOut> {
  return patchJson(`${BASE}/${id}`, input);
}

export function archiveIdea(id: string): Promise<IdeaOut> {
  return postJson(`${BASE}/${id}/archive`);
}

export function restoreIdea(id: string): Promise<IdeaOut> {
  return postJson(`${BASE}/${id}/restore`);
}

/** Send the idea for scoring. The AI proposes a 1 to 10 score per dimension in the
 * background: poll getAssessment until proposal_status is "ready" or "failed". */
export function requestAssessment(ideaId: string): Promise<IqAssessmentOut> {
  return postJson(`${BASE}/${ideaId}/assessments`);
}

export function getAssessment(ideaId: string, assessmentId: string): Promise<IqAssessmentOut> {
  return getJson(`${BASE}/${ideaId}/assessments/${assessmentId}`);
}

/** Autosave of the owner's review: changed scores (null puts the proposal back) and notes. */
export function saveReview(
  ideaId: string,
  assessmentId: string,
  review: ReviewIn,
): Promise<IqAssessmentOut> {
  return patchJson(`${BASE}/${ideaId}/assessments/${assessmentId}/review`, review);
}

export function confirmAssessment(ideaId: string, assessmentId: string): Promise<IqAssessmentOut> {
  return postJson(`${BASE}/${ideaId}/assessments/${assessmentId}/confirm`);
}

/** Where an idea's latest assessment lives, if it has one. */
export function assessmentHref(idea: Pick<IdeaSummaryOut, "id" | "latest_assessment">): string | null {
  return idea.latest_assessment
    ? `/ideas/${idea.id}/assessments/${idea.latest_assessment.id}`
    : null;
}
