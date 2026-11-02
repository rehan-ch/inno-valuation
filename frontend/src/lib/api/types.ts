// Types for the InnoValuation API (/api/v1).
// Response and request types come from schema.d.ts, which `npm run gen:api` generates
// from openapi.json (the backend's OpenAPI schema). Do not hand-write API shapes here;
// add a one-line alias for each schema the frontend uses.
import type { components } from "./schema";

type Schemas = components["schemas"];

export type HealthOut = Schemas["HealthOut"];
export type MessageOut = Schemas["MessageOut"];

export type MeOut = Schemas["MeOut"];
export type MembershipOut = Schemas["MembershipOut"];
export type ConsultantOrganisationOut = Schemas["ConsultantOrganisationOut"];
export type MembershipRole = Schemas["MembershipRole"];
export type OrgRole = Schemas["OrgRole"];

export type OrganisationOut = Schemas["OrganisationOut"];
export type OrganisationCreateIn = Schemas["OrganisationCreateIn"];
export type OrganisationUpdateIn = Schemas["OrganisationUpdateIn"];
export type OrganisationStatus = Schemas["OrganisationStatus"];

export type MemberOut = Schemas["MemberOut"];
export type InvitationOut = Schemas["InvitationOut"];
export type InvitationPreviewOut = Schemas["InvitationPreviewOut"];

export type QuestionSetOut = Schemas["QuestionSetOut"];
export type ReadinessStatus = Schemas["ReadinessStatus"];
export type AssessmentSummaryOut = Schemas["AssessmentSummaryOut"];
export type AssessmentOut = Schemas["AssessmentOut"];
export type ConsensusOut = Schemas["ConsensusOut"];
export type QuestionConsensusOut = Schemas["QuestionConsensusOut"];
export type ResultOut = Schemas["ResultOut"];
export type ExplanationOut = Schemas["ExplanationOut"];

export type IdeaStage = Schemas["IdeaStage"];
export type IdeaStatus = Schemas["IdeaStatus"];
export type IqAssessmentStatus = Schemas["IqAssessmentStatus"];
export type IdeaCreateIn = Schemas["IdeaCreateIn"];
export type IdeaUpdateIn = Schemas["IdeaUpdateIn"];
export type IdeaSummaryOut = Schemas["IdeaSummaryOut"];
export type IdeaOut = Schemas["IdeaOut"];
export type AssessmentBriefOut = Schemas["AssessmentBriefOut"];
export type IqAssessmentOut = Schemas["IqAssessmentOut"];
export type DimensionReviewOut = Schemas["DimensionReviewOut"];
export type IqCategoryOut = Schemas["IqCategoryOut"];
export type IqPriorityOut = Schemas["IqPriorityOut"];
export type LevelOut = Schemas["LevelOut"];
export type VfmOut = Schemas["VfmOut"];
export type ReviewIn = Schemas["ReviewIn"];
export type ProposalStatus = AssessmentBriefOut["proposal_status"];

export type ConsultantGrantOut = Schemas["ConsultantGrantOut"];
export type ConsultantAccessOut = Schemas["ConsultantAccessOut"];
export type GrantStatus = Schemas["GrantStatus"];

// Hand-written on purpose: the backend's exception handlers return this envelope for
// every error, but no route declares it as a response model, so it is not in
// openapi.json yet. Keep it in line with backend/app/core/errors.py.
export interface ApiErrorEnvelope {
  error: {
    code: string;
    message: string;
  };
}
