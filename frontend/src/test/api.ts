// Test helpers: a fetch stub keyed by "METHOD /api/v1/path", and canned API objects.
import { vi } from "vitest";

import type {
  AssessmentOut,
  AssessmentSummaryOut,
  AuditEventOut,
  CompassOut,
  DashboardOut,
  DimensionDetailOut,
  TargetsOut,
  ConsultantAccessOut,
  ConsultantGrantOut,
  DimensionReviewOut,
  IdeaOut,
  IdeaSummaryOut,
  InvitationOut,
  IqAssessmentOut,
  MemberOut,
  MeOut,
  OrganisationOut,
  QuestionSetOut,
  WeightsChangeOut,
  WeightsOut,
} from "@/lib/api/types";

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export function errorResponse(
  code: string,
  message: string,
  status: number,
): Response {
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
        body:
          typeof init?.body === "string" ? JSON.parse(init.body) : undefined,
        headers: new Headers(init?.headers),
      };
      calls.push(call);
      const key = `${method} ${url.pathname}`;
      if (!(key in handlers)) throw new TypeError(`Unexpected request: ${key}`);
      const handler = handlers[key];
      const result =
        typeof handler === "function" ? await handler(call) : handler;
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
    ai_enabled: true,
    ...overrides,
  };
}

export function fakeOrganisation(
  overrides: Partial<OrganisationOut> = {},
): OrganisationOut {
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

export function fakeInvitation(
  overrides: Partial<InvitationOut> = {},
): InvitationOut {
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

export function fakeGrant(
  overrides: Partial<ConsultantGrantOut> = {},
): ConsultantGrantOut {
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

export function fakeAccess(
  overrides: Partial<ConsultantAccessOut> = {},
): ConsultantAccessOut {
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

export function fakeAssessment(
  overrides: Partial<AssessmentOut> = {},
): AssessmentOut {
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
    scale: {
      min: 1,
      max: 5,
      labels: { "1": "Strongly Disagree", "5": "Strongly Agree" },
    },
    categories: [
      { key: "customer_facing", name: "Customer-Facing Innovation", order: 1 },
    ],
    dimensions: [
      {
        key: "customer_journey",
        name: "Customer Journey",
        order: 1,
        category: "customer_facing",
        description: "Map the customer's journey.",
        questions: [
          {
            id: "customer_journey_1",
            text: "Do you understand the end-to-end experience?",
          },
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

export const IDEA_ID = "88888888-8888-8888-8888-888888888888";
export const IQ_ASSESSMENT_ID = "99999999-9999-9999-9999-999999999999";

export function fakeIdeaSummary(
  overrides: Partial<IdeaSummaryOut> = {},
): IdeaSummaryOut {
  return {
    id: IDEA_ID,
    title: "Same-day delivery",
    stage: "prototype",
    status: "draft",
    archived: false,
    currency: "USD",
    investment: "50000.00",
    expected_value: null,
    created_by_name: "Mia Member",
    created_at: "2026-10-28T09:00:00Z",
    updated_at: "2026-10-28T09:00:00Z",
    latest_assessment: null,
    ...overrides,
  };
}

export function fakeIdea(overrides: Partial<IdeaOut> = {}): IdeaOut {
  return {
    ...fakeIdeaSummary(),
    summary: "Local shops deliver within two hours.",
    problem: null,
    target_market: null,
    uniqueness: null,
    team: null,
    risks: null,
    can_change: true,
    can_archive: true,
    assessments: [],
    ...overrides,
  };
}

const DIMENSIONS: [string, string, number, string][] = [
  ["customer_journey", "Customer Journey", 1, "customer_facing"],
  ["brand_magnetism", "Brand Magnetism", 2, "customer_facing"],
  ["organizational_agility", "Organizational Agility", 7, "process"],
];

/** A small assessment (3 dimensions) shaped like the real one. */
export function fakeIqAssessment(
  overrides: Partial<IqAssessmentOut> = {},
): IqAssessmentOut {
  const dimensions: DimensionReviewOut[] = DIMENSIONS.map(
    ([key, name, order, category]) => ({
      key,
      name,
      order,
      category,
      description: `About ${name}.`,
      proposed_score: 4,
      proposed_rationale: [
        "The idea says a little about this.",
        "So a middle score fits.",
      ],
      proposed_confidence: "0.70",
      final_score: null,
      level: null,
      note: null,
      changed: false,
    }),
  );
  return {
    id: IQ_ASSESSMENT_ID,
    idea_id: IDEA_ID,
    idea_title: "Same-day delivery",
    status: "proposed",
    proposal_status: "ready",
    sample: false,
    question_set_version: 1,
    scale: { min: 1, max: 10 },
    levels: [
      {
        key: "continuous_improvement",
        name: "Continuous Improvement",
        min: 1,
        max: 3,
        text: "Incremental.",
      },
      { key: "innovation", name: "Innovation", min: 4, max: 6, text: "Novel." },
      {
        key: "invention",
        name: "Invention",
        min: 7,
        max: 10,
        text: "Breakthrough.",
      },
    ],
    dimensions,
    missing_information: [],
    iq: null,
    iq_maximum: "100.0",
    categories: [
      {
        key: "customer_facing",
        name: "Customer-Facing Innovation",
        score: null,
        maximum: "100.0",
      },
    ],
    priorities: [],
    strengths: [],
    compass: null,
    custom_weights: false,
    vfm: null,
    can_review: true,
    requested_at: "2026-10-28T09:05:00Z",
    requested_by_name: "Mia Member",
    confirmed_at: null,
    confirmed_by_name: null,
    ...overrides,
  };
}

export function fakeConfirmedAssessment(
  overrides: Partial<IqAssessmentOut> = {},
): IqAssessmentOut {
  const base = fakeIqAssessment();
  return {
    ...base,
    status: "confirmed",
    dimensions: base.dimensions.map((d, i) => ({
      ...d,
      final_score: i === 2 ? 5 : 4,
      changed: i === 2,
      note: i === 2 ? "The team has reorganised twice this year." : null,
      level: {
        key: "innovation",
        name: "Innovation",
        min: 4,
        max: 6,
        text: "Novel.",
      },
    })),
    iq: "70.0",
    categories: [
      {
        key: "customer_facing",
        name: "Customer-Facing Innovation",
        score: "74.0",
        maximum: "100.0",
      },
    ],
    priorities: [
      {
        rank: 1,
        key: "organizational_agility",
        name: "Organizational Agility",
        score: 5,
        level_name: "Innovation",
        next_steps: "Build adaptable structures.",
      },
    ],
    custom_weights: false,
    vfm: {
      investment: "50000.00",
      currency: "USD",
      per_point: "714.29",
      not_calculable_reason: null,
    },
    can_review: false,
    confirmed_at: "2026-10-28T10:00:00Z",
    confirmed_by_name: "Mia Member",
    ...overrides,
  };
}

const ALL_DIMENSIONS: [string, string, string][] = [
  ["customer_journey", "Customer Journey", "customer_facing"],
  ["brand_magnetism", "Brand Magnetism", "customer_facing"],
  ["channel_navigation", "Channel Navigation", "customer_facing"],
  ["service_excellence", "Service Excellence", "customer_facing"],
  ["product_evolution", "Product Evolution", "process"],
  ["operational_efficiency", "Operational Efficiency", "process"],
  ["organizational_agility", "Organizational Agility", "process"],
  ["collaborative_synergy", "Collaborative Synergy", "process"],
  ["value_creation_engine", "Value Creation Engine", "strategic"],
  ["sustainable_future", "Sustainable Future", "strategic"],
  ["data_intelligence", "Data Intelligence", "strategic"],
  ["financial_imperative", "Financial Imperative", "strategic"],
];

/** Every dimension counting equally, unless `weights` says otherwise for some keys. */
export function fakeWeights(
  weights: Record<string, string> = {},
  overrides: Partial<WeightsOut> = {},
): WeightsOut {
  return {
    question_set_version: 1,
    weights: ALL_DIMENSIONS.map(([key, name, category], i) => ({
      key,
      name,
      order: i + 1,
      category,
      weight: weights[key] ?? "1",
    })),
    custom: Object.values(weights).some((w) => w !== "1"),
    set_at: null,
    set_by_name: null,
    can_change: true,
    limits: { minimum: 0, maximum: 1000, max_decimal_places: 6 },
    ...overrides,
  };
}

export function fakeWeightsChange(
  overrides: Partial<WeightsChangeOut> = {},
): WeightsChangeOut {
  return {
    id: "77777777-7777-7777-7777-777777777771",
    set_at: "2026-11-03T09:00:00Z",
    set_by_name: "Olive Owner",
    custom: true,
    weights: Object.fromEntries(
      ALL_DIMENSIONS.map(([key]) => [
        key,
        key === "data_intelligence" ? "3" : "1",
      ]),
    ),
    ...overrides,
  };
}

const COMPASS_DIMENSIONS: [string, string, number, string][] = [
  ["customer_journey", "Customer Journey", 1, "customer_facing"],
  ["brand_magnetism", "Brand Magnetism", 2, "customer_facing"],
  ["operational_efficiency", "Operational Efficiency", 6, "process"],
  ["organizational_agility", "Organizational Agility", 7, "process"],
  ["data_intelligence", "Data Intelligence", 11, "strategic"],
  ["financial_imperative", "Financial Imperative", 12, "strategic"],
];

const IQ_LEVELS = [
  { key: "continuous_improvement", name: "Continuous Improvement", order: 1, min: 1, max: 3, text: "Incremental." },
  { key: "innovation", name: "Innovation", order: 2, min: 4, max: 6, text: "Novel." },
  { key: "invention", name: "Invention", order: 3, min: 7, max: 10, text: "Breakthrough." },
];

/** A small compass (6 dimensions in 3 categories) shaped like the real one. The scores are
 * arbitrary: the page shows what it is sent. */
export function fakeCompass(scale: "readiness" | "iq", scores?: number[]): CompassOut {
  const readiness = scale === "readiness";
  const values = scores ?? (readiness ? [20, 20, 15, 15, 12, 18] : [8, 7, 6, 3, 8, 5]);
  const maximum = readiness ? 25 : 10;
  const levelOf = (score: number) => {
    const level = IQ_LEVELS.find((l) => score >= l.min && score <= l.max) ?? IQ_LEVELS[0]!;
    return { key: level.key, name: level.name, order: level.order };
  };
  const categories: [string, string][] = [
    ["customer_facing", "Customer-Facing Innovation"],
    ["process", "Process Innovation"],
    ["strategic", "Strategic Innovation"],
  ];
  return {
    scale,
    question_set_version: 1,
    minimum: readiness ? 5 : 1,
    maximum,
    segments: COMPASS_DIMENSIONS.map(([key, name, order, category], i) => ({
      key,
      name,
      order,
      category,
      score: values[i] ?? 0,
      maximum,
      level: readiness ? null : levelOf(values[i] ?? 1),
      priority_rank: null,
      target: null,
      gap: null,
    })),
    categories: categories.map(([key, name], i) => ({
      key,
      name,
      order: i + 1,
      score: readiness ? "40" : "75.0",
      maximum: readiness ? "50" : "100.0",
      dimension_keys: COMPASS_DIMENSIONS.filter((d) => d[3] === key).map((d) => d[0]),
    })),
    levels: readiness ? [] : IQ_LEVELS,
  };
}

export const EMPTY_DASHBOARD: DashboardOut = { readiness: null, ideas: [], iq: null };

/** A dashboard with both scores: readiness 190 (Building Blocks) and an idea's IQ 70.0. */
export function fakeDashboard(overrides: Partial<DashboardOut> = {}): DashboardOut {
  return {
    readiness: {
      assessment_id: "55555555-5555-5555-5555-555555555555",
      finalised_at: "2026-10-20T10:00:00Z",
      question_set_version: 1,
      total: 190,
      total_maximum: 300,
      band: {
        key: "building_blocks",
        name: "Building Blocks",
        text: "You have a strong foundation but may need to focus on specific weaknesses.",
      },
      compass: fakeCompass("readiness"),
      priorities: [
        {
          rank: 1,
          key: "data_intelligence",
          name: "Data Intelligence",
          score: 12,
          maximum: 25,
          level_name: null,
          next_steps: "Invest in analytics capabilities.",
        },
      ],
    },
    ideas: [
      {
        idea_id: IDEA_ID,
        title: "Same-day delivery",
        assessment_id: IQ_ASSESSMENT_ID,
        iq: "70.0",
        confirmed_at: "2026-10-28T09:30:00Z",
      },
    ],
    iq: {
      idea_id: IDEA_ID,
      idea_title: "Same-day delivery",
      assessment_id: IQ_ASSESSMENT_ID,
      confirmed_at: "2026-10-28T09:30:00Z",
      question_set_version: 1,
      iq: "70.0",
      iq_maximum: "100.0",
      vfm: {
        investment: "50000.00",
        currency: "USD",
        per_point: "714.29",
        not_calculable_reason: null,
      },
      custom_weights: false,
      compass: fakeCompass("iq"),
      priorities: [
        {
          rank: 1,
          key: "organizational_agility",
          name: "Organizational Agility",
          score: 3,
          maximum: 10,
          level_name: "Continuous Improvement",
          next_steps: "Adopt agile ways of working.",
        },
      ],
    },
    ...overrides,
  };
}

export function fakeDimensionDetail(
  overrides: Partial<DimensionDetailOut> = {},
): DimensionDetailOut {
  return {
    key: "organizational_agility",
    name: "Organizational Agility",
    order: 7,
    category: { key: "process", name: "Process Innovation", order: 2 },
    description: "How quickly the organisation adapts.",
    sub_aspects: ["Decision speed", "Team structure"],
    next_steps: "Adopt agile ways of working.",
    previous: { key: "operational_efficiency", name: "Operational Efficiency", order: 6 },
    next: { key: "collaborative_synergy", name: "Collaborative Synergy", order: 8 },
    readiness: {
      assessment_id: "55555555-5555-5555-5555-555555555555",
      finalised_at: "2026-10-20T10:00:00Z",
      question_set_version: 1,
      score: 15,
      maximum: 25,
      priority_rank: 5,
      target: 20,
      gap: 5,
      answer_scale: { min: 1, max: 5, labels: { "1": "Strongly Disagree", "5": "Strongly Agree" } },
      questions: [
        { id: "organizational_agility_1", text: "We adapt quickly to change.", answer: 3 },
        { id: "organizational_agility_2", text: "Teams can reorganise themselves.", answer: 4 },
      ],
      history: [
        {
          assessment_id: "55555555-5555-5555-5555-555555555555",
          at: "2026-10-20T10:00:00Z",
          score: 15,
          maximum: 25,
          change: 2,
          direction: "up",
        },
        {
          assessment_id: "66666666-6666-6666-6666-666666666666",
          at: "2026-09-01T10:00:00Z",
          score: 13,
          maximum: 25,
          change: null,
          direction: null,
        },
      ],
    },
    ideas: [
      {
        idea_id: IDEA_ID,
        title: "Same-day delivery",
        assessment_id: IQ_ASSESSMENT_ID,
        iq: "70.0",
        confirmed_at: "2026-10-28T09:30:00Z",
      },
    ],
    iq: {
      idea_id: IDEA_ID,
      idea_title: "Same-day delivery",
      assessment_id: IQ_ASSESSMENT_ID,
      confirmed_at: "2026-10-28T09:30:00Z",
      question_set_version: 1,
      score: 5,
      maximum: 10,
      level: { key: "innovation", name: "Innovation", min: 4, max: 6, text: "Novel." },
      proposed_score: 4,
      changed: true,
      rationale: ["The idea says the team reorganised.", "So a middle score fits."],
      note: "The team has reorganised twice this year.",
      priority_rank: 1,
      target: 8,
      gap: 3,
      history: [],
    },
    ...overrides,
  };
}

export function fakeTargets(overrides: Partial<TargetsOut> = {}): TargetsOut {
  const rows = (targets: Record<string, number>) =>
    COMPASS_DIMENSIONS.map(([key, name, order, category]) => ({
      key,
      name,
      order,
      category,
      target: targets[key] ?? null,
    }));
  return {
    question_set_version: 1,
    readiness: {
      scale: "readiness",
      minimum: 5,
      maximum: 25,
      targets: rows({ customer_journey: 22 }),
      set_at: "2026-11-01T09:00:00Z",
      set_by_name: "Olive Owner",
    },
    iq: {
      scale: "iq",
      minimum: 1,
      maximum: 10,
      targets: rows({}),
      set_at: null,
      set_by_name: null,
    },
    can_change: true,
    ...overrides,
  };
}

export function fakeAuditEvent(overrides: Partial<AuditEventOut> = {}): AuditEventOut {
  return {
    id: "77777777-7777-7777-7777-777777777777",
    at: "2026-11-02T09:30:00Z",
    action: "iq.confirmed",
    action_label: "Idea scores confirmed",
    actor_id: "11111111-1111-1111-1111-111111111111",
    actor_name: "Olive Owner",
    subject: "Same-day delivery",
    detail: "Changed from the AI's proposal: Organizational Agility.",
    question_set_version: 1,
    ai_model: "claude-opus-5-5",
    ...overrides,
  };
}
