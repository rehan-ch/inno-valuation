import type { IdeaStage, IdeaStatus, IqAssessmentStatus, ProposalStatus } from "@/lib/api/types";

export const STAGE_LABELS: Record<IdeaStage, string> = {
  idea: "Idea",
  concept: "Concept",
  prototype: "Prototype",
  pilot: "Pilot",
  launched: "Launched",
};

export const STAGES = Object.keys(STAGE_LABELS) as IdeaStage[];

export const IDEA_STATUS_LABELS: Record<IdeaStatus, string> = {
  draft: "Draft",
  submitted: "Being scored",
  assessed: "Scored",
};

export const IDEA_STATUS_TONES: Record<IdeaStatus, "neutral" | "amber" | "green" | "blue"> = {
  draft: "neutral",
  submitted: "amber",
  assessed: "green",
};

export const ASSESSMENT_STATUS_LABELS: Record<IqAssessmentStatus, string> = {
  proposed: "Proposed by AI",
  confirmed: "Confirmed",
  superseded: "Replaced",
};

/** What an assessment is doing right now, in plain words. */
export function assessmentLabel(status: IqAssessmentStatus, proposal: ProposalStatus): string {
  if (status === "confirmed") return "Confirmed";
  if (status === "superseded") return "Replaced";
  if (proposal === "pending") return "AI is proposing scores";
  if (proposal === "failed") return "Proposal failed";
  return "Ready to review";
}
