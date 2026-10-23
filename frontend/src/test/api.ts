// Test helpers: a fetch stub keyed by "METHOD /api/v1/path", and canned API objects.
import { vi } from "vitest";

import type {
  AssessmentOut,
  AssessmentSummaryOut,
  ConsultantAccessOut,
  ConsultantGrantOut,
  InvitationOut,
  MemberOut,
  MeOut,
  OrganisationOut,
  QuestionSetOut,
} from "@/lib/api/types";

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export function errorResponse(code: string, message: string, status: number): Response {
  return jsonResponse({ error: { code, message } }, status);
}

export interface RecordedCall {
  method: string;
  path: string;
  body?: unknown;
  headers: Headers;
}

type Handler = unknown | ((call: RecordedCall) => unknown);

/** Stubs fetch. Keys look like "POST /api/v1/auth/sign-in"; a handler is a response body,
 * a Response, or a function of the recorded call. Unexpected requests fail the test. */
export function stubApi(handlers: Record<string, Handler>): RecordedCall[] {
  const calls: RecordedCall[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      const method = (init?.method ?? "GET").toUpperCase();
      const call: RecordedCall = {
        method,
        path: url.pathname,
        body: typeof init?.body === "string" ? JSON.parse(init.body) : undefined,
        headers: new Headers(init?.headers),
      };
      calls.push(call);
      const key = `${method} ${url.pathname}`;
      if (!(key in handlers)) throw new TypeError(`Unexpected request: ${key}`);
      const handler = handlers[key];
      const result = typeof handler === "function" ? await handler(call) : handler;
      return result instanceof Response ? result : jsonResponse(result);
    }),
  );
  return calls;
}

export function fakeMe(overrides: Partial<MeOut> = {}): MeOut {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    email: "owner@example.com",
    name: "Olive Owner",
    email_verified: true,
    active_organisation_id: "22222222-2222-2222-2222-222222222222",
    memberships: [
      {
        organisation_id: "22222222-2222-2222-2222-222222222222",
        organisation_name: "Acme",
        organisation_status: "active",
        role: "owner",
      },
    ],
    consultant_organisations: [],
    ...overrides,
  };
}

export function fakeOrganisation(overrides: Partial<OrganisationOut> = {}): OrganisationOut {
  return {
    id: "22222222-2222-2222-2222-222222222222",
    name: "Acme",
    description: null,
    industry: null,
    country: null,
    size_band: null,
    revenue_band: null,
    founder_names: null,
    website: null,
    primary_contact_name: null,
    primary_contact_email: null,
    currency: "USD",
    status: "active",
    role: "owner",
    ...overrides,
  };
}

export function fakeMember(overrides: Partial<MemberOut> = {}): MemberOut {
  return {
    id: "33333333-3333-3333-3333-333333333333",
    user_id: "11111111-1111-1111-1111-111111111111",
    name: "Olive Owner",
    email: "owner@example.com",
    role: "owner",
    joined_at: "2026-10-01T10:00:00Z",
    ...overrides,
  };
}

export function fakeInvitation(overrides: Partial<InvitationOut> = {}): InvitationOut {
  return {
    id: "44444444-4444-4444-4444-444444444444",
    email: "new@example.com",
    role: "member",
    invited_by_name: "Olive Owner",
    created_at: "2026-10-14T10:00:00Z",
    expires_at: "2026-10-21T10:00:00Z",
    expired: false,
    ...overrides,
  };
}

export function fakeGrant(overrides: Partial<ConsultantGrantOut> = {}): ConsultantGrantOut {
  return {
    id: "55555555-5555-5555-5555-555555555555",
    email: "amy@example.com",
    status: "waiting",
    expires_at: "2026-12-31T23:59:59Z",
    created_at: "2026-10-14T10:00:00Z",
    accepted_at: null,
    revoked_at: null,
    ...overrides,
  };
}

export function fakeAccess(overrides: Partial<ConsultantAccessOut> = {}): ConsultantAccessOut {
  return {
    id: "55555555-5555-5555-5555-555555555555",
    organisation_id: "22222222-2222-2222-2222-222222222222",
    organisation_name: "Acme",
    organisation_status: "active",
    status: "waiting",
    expires_at: "2026-12-31T23:59:59Z",
    ...overrides,
  };
}

export function fakeAssessmentSummary(
  overrides: Partial<AssessmentSummaryOut> = {},
): AssessmentSummaryOut {
  return {
    id: "77777777-7777-7777-7777-777777777777",
    status: "collecting",
    question_set_version: 1,
    created_at: "2026-10-20T09:00:00Z",
    started_at: "2026-10-20T09:00:00Z",
    finalised_at: null,
    created_by_name: "Olive Owner",
    submitted_count: 0,
    my_status: "not_started",
    total: null,
    band_name: null,
    ...overrides,
  };
}

export function fakeAssessment(overrides: Partial<AssessmentOut> = {}): AssessmentOut {
  return {
    ...fakeAssessmentSummary(),
    my_answers: {},
    my_submitted_at: null,
    question_count: 4,
    can_answer: true,
    can_manage: true,
    participants: [],
    ...overrides,
  };
}

/** A small question set (2 dimensions, 2 questions each) shaped like the real one. */
export function fakeQuestionSet(): QuestionSetOut {
  return {
    version: 1,
    scale: { min: 1, max: 5, labels: { "1": "Strongly Disagree", "5": "Strongly Agree" } },
    categories: [{ key: "customer_facing", name: "Customer-Facing Innovation", order: 1 }],
    dimensions: [
      {
        key: "customer_journey",
        name: "Customer Journey",
        order: 1,
        category: "customer_facing",
        description: "Map the customer's journey.",
        questions: [
          { id: "customer_journey_1", text: "Do you understand the end-to-end experience?" },
          { id: "customer_journey_2", text: "Is feedback integrated?" },
        ],
      },
      {
        key: "brand_magnetism",
        name: "Brand Magnetism",
        order: 2,
        category: "customer_facing",
        description: "Build a magnetic brand.",
        questions: [
          { id: "brand_magnetism_1", text: "Are brand values clear?" },
          { id: "brand_magnetism_2", text: "Does the story resonate?" },
        ],
      },
    ],
  };
}
