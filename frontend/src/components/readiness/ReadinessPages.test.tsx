import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ConsensusOut, ResultOut } from "@/lib/api/types";
import {
  fakeAssessment,
  fakeAssessmentSummary,
  fakeMe,
  fakeQuestionSet,
  stubApi,
} from "@/test/api";
import type { RecordedCall } from "@/test/api";
import { renderWithMe } from "@/test/me";
import { routerPush } from "@/test/navigation";

import { ConsensusPage } from "./ConsensusPage";
import { QuestionnairePage } from "./QuestionnairePage";
import { ReadinessListPage } from "./ReadinessListPage";
import { ResultPage } from "./ResultPage";

vi.mock("next/navigation", async () => (await import("@/test/navigation")).navigationMock());

const ID = "77777777-7777-7777-7777-777777777777";
const A = `/api/v1/readiness/assessments/${ID}`;
const ALL = {
  customer_journey_1: 3,
  customer_journey_2: 4,
  brand_magnetism_1: 3,
  brand_magnetism_2: 2,
};

describe("ReadinessListPage", () => {
  it("lets an owner start an assessment and opens it", async () => {
    routerPush.mockClear();
    const calls = stubApi({
      "GET /api/v1/readiness/assessments": [],
      "POST /api/v1/readiness/assessments": fakeAssessment(),
    });
    const user = userEvent.setup();

    renderWithMe(<ReadinessListPage />, fakeMe());
    await user.click(await screen.findByRole("button", { name: "Start a readiness assessment" }));

    expect(calls.at(-1)).toMatchObject({ method: "POST", path: "/api/v1/readiness/assessments" });
    expect(routerPush).toHaveBeenCalledWith(`/readiness/${ID}`);
  });

  it("shows a final assessment's score and links to its result", async () => {
    stubApi({
      "GET /api/v1/readiness/assessments": [
        fakeAssessmentSummary({ status: "final", total: 190, band_name: "Building Blocks" }),
      ],
    });

    renderWithMe(<ReadinessListPage />, fakeMe());

    expect(await screen.findByText("190 out of 300 · Building Blocks")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "See the result" })).toHaveAttribute(
      "href",
      `/readiness/${ID}/result`,
    );
    // No second assessment while one is open, but a final one does not block.
    expect(screen.getByRole("button", { name: "Start a readiness assessment" })).toBeInTheDocument();
  });
});

describe("QuestionnairePage", () => {
  it("saves each answer as it is chosen and shows it saved", async () => {
    const calls = stubApi({
      [`GET ${A}`]: fakeAssessment(),
      "GET /api/v1/readiness/question-set": fakeQuestionSet(),
      [`PATCH ${A}/my-answers`]: (call: RecordedCall) =>
        fakeAssessment({ my_answers: (call.body as { answers: Record<string, number> }).answers }),
    });
    const user = userEvent.setup();

    renderWithMe(<QuestionnairePage assessmentId={ID} />, fakeMe());
    const question = await screen.findByRole("group", {
      name: "Do you understand the end-to-end experience?",
    });
    await user.click(within(question).getByRole("radio", { name: "4" }));

    expect(calls.at(-1)).toMatchObject({
      method: "PATCH",
      path: `${A}/my-answers`,
      body: { answers: { customer_journey_1: 4 } },
    });
    expect(await screen.findByText("Saved")).toBeInTheDocument();
    expect(screen.getByText("1 of 4 answered")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Submit my answers" })).toBeDisabled();
  });

  it("submits once every question is answered, after a confirmation", async () => {
    const calls = stubApi({
      [`GET ${A}`]: fakeAssessment({ my_answers: ALL, my_status: "in_progress" }),
      "GET /api/v1/readiness/question-set": fakeQuestionSet(),
      [`POST ${A}/my-answers/submit`]: fakeAssessment({
        my_answers: ALL,
        my_status: "submitted",
        my_submitted_at: "2026-10-21T10:00:00Z",
      }),
    });
    const user = userEvent.setup();

    renderWithMe(<QuestionnairePage assessmentId={ID} />, fakeMe());
    await user.click(await screen.findByRole("button", { name: "Submit my answers" }));
    await user.click(screen.getByRole("button", { name: "Submit now" }));

    expect(calls.at(-1)).toMatchObject({ method: "POST", path: `${A}/my-answers/submit` });
    expect(await screen.findByText(/Your answers are submitted/)).toBeInTheDocument();
    // Submitted answers are locked.
    const question = screen.getByRole("group", { name: "Is feedback integrated?" });
    expect(within(question).getByRole("radio", { name: "4" })).toBeDisabled();
  });

  it("shows the facilitator everyone's progress and starts agreeing answers", async () => {
    routerPush.mockClear();
    const calls = stubApi({
      [`GET ${A}`]: fakeAssessment({
        submitted_count: 1,
        participants: [
          { name: "Mia Member", answered: 4, submitted_at: "2026-10-21T09:00:00Z" },
          { name: "Late Larry", answered: 1, submitted_at: null },
        ],
      }),
      "GET /api/v1/readiness/question-set": fakeQuestionSet(),
      [`POST ${A}/consensus/begin`]: {},
    });
    const user = userEvent.setup();

    renderWithMe(<QuestionnairePage assessmentId={ID} />, fakeMe());
    expect(await screen.findByText("1 of 4 answered")).toBeInTheDocument(); // Late Larry
    await user.click(screen.getByRole("button", { name: "Start agreeing answers" }));
    expect(screen.getByText("Close answering with 1 submitted?")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Yes, start agreeing" }));

    expect(calls.at(-1)).toMatchObject({ method: "POST", path: `${A}/consensus/begin` });
    expect(routerPush).toHaveBeenCalledWith(`/readiness/${ID}/consensus`);
  });

  it("tells an investor that their role watches", async () => {
    stubApi({
      [`GET ${A}`]: fakeAssessment({ can_answer: false, can_manage: false, my_answers: null }),
      "GET /api/v1/readiness/question-set": fakeQuestionSet(),
    });

    renderWithMe(<QuestionnairePage assessmentId={ID} />, fakeMe());

    expect(
      await screen.findByText("Your role watches the assessment; it does not answer."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Submit my answers" })).not.toBeInTheDocument();
  });
});

function fakeConsensus(agreed: Record<string, number | null> = {}): ConsensusOut {
  const question = (id: string, dim: string, answers: number[]) => ({
    question_id: id,
    dimension_key: dim,
    answers: answers.map((answer, i) => ({ name: ["Olive", "Mia"][i] ?? "X", answer })),
    mean: (answers.reduce((s, a) => s + a, 0) / answers.length).toFixed(2),
    spread: Math.max(...answers) - Math.min(...answers),
    wide_spread: Math.max(...answers) - Math.min(...answers) >= 2,
    agreed: agreed[id] ?? null,
    note: null,
  });
  return {
    assessment_id: ID,
    status: "consensus",
    participants: ["Olive", "Mia"],
    agreed_count: Object.values(agreed).filter((v) => v !== null).length,
    question_count: 4,
    questions: [
      question("customer_journey_1", "customer_journey", [2, 5]),
      question("customer_journey_2", "customer_journey", [4, 4]),
      question("brand_magnetism_1", "brand_magnetism", [3, 3]),
      question("brand_magnetism_2", "brand_magnetism", [1, 2]),
    ],
  };
}

describe("ConsensusPage", () => {
  it("shows everyone's answers with the mean and spread, and saves an agreed answer", async () => {
    const calls = stubApi({
      [`GET ${A}`]: fakeAssessment({ status: "consensus" }),
      [`GET ${A}/consensus`]: fakeConsensus(),
      "GET /api/v1/readiness/question-set": fakeQuestionSet(),
      [`PATCH ${A}/consensus`]: fakeConsensus({ customer_journey_1: 4 }),
    });
    const user = userEvent.setup();

    renderWithMe(<ConsensusPage assessmentId={ID} />, fakeMe());
    const question = await screen.findByRole("group", {
      name: "Do you understand the end-to-end experience?",
    });
    expect(within(question).getByText("3.50")).toBeInTheDocument();
    expect(within(question).getByText("Discuss: answers differ")).toBeInTheDocument();
    await user.click(within(question).getByRole("radio", { name: "Agreed answer 4" }));

    expect(calls.at(-1)).toMatchObject({
      method: "PATCH",
      path: `${A}/consensus`,
      body: { answers: { customer_journey_1: 4 }, notes: {} },
    });
    expect(await screen.findByText("1 of 4 agreed")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Finalise the result" })).toBeDisabled();
  });

  it("finalises once every answer is agreed and opens the result", async () => {
    routerPush.mockClear();
    const calls = stubApi({
      [`GET ${A}`]: fakeAssessment({ status: "consensus" }),
      [`GET ${A}/consensus`]: fakeConsensus(ALL),
      "GET /api/v1/readiness/question-set": fakeQuestionSet(),
      [`POST ${A}/finalise`]: {},
    });
    const user = userEvent.setup();

    renderWithMe(<ConsensusPage assessmentId={ID} />, fakeMe());
    await user.click(await screen.findByRole("button", { name: "Finalise the result" }));
    await user.click(screen.getByRole("button", { name: "Finalise now" }));

    expect(calls.at(-1)).toMatchObject({ method: "POST", path: `${A}/finalise` });
    expect(routerPush).toHaveBeenCalledWith(`/readiness/${ID}/result`);
  });
});

describe("ResultPage", () => {
  it("shows the total, the band in the book's words, priorities and their next steps", async () => {
    const result: ResultOut = {
      assessment_id: ID,
      question_set_version: 1,
      total: 190,
      total_maximum: 300,
      band: {
        key: "building_blocks",
        name: "Building Blocks",
        text: "You have a strong foundation but may need to focus on specific weaknesses.",
      },
      dimensions: [
        { key: "customer_journey", name: "Customer Journey", order: 1, category: "customer_facing", score: 20, maximum: 25 },
        { key: "channel_navigation", name: "Channel Navigation", order: 3, category: "customer_facing", score: 15, maximum: 25 },
      ],
      categories: [{ key: "customer_facing", name: "Customer-Facing Innovation", score: 85, maximum: 125 }],
      priorities: [
        {
          rank: 1,
          key: "channel_navigation",
          name: "Channel Navigation",
          score: 15,
          maximum: 25,
          next_steps: "If scoring low, streamline channels.",
        },
      ],
      strengths: [
        { key: "customer_journey", name: "Customer Journey", order: 1, category: "customer_facing", score: 20, maximum: 25 },
      ],
      submitted_count: 3,
      finalised_at: "2026-10-21T12:00:00Z",
    };
    stubApi({ [`GET ${A}/result`]: result });

    renderWithMe(<ResultPage assessmentId={ID} />, fakeMe());

    const total = await screen.findByRole("region", { name: "Total" });
    expect(within(total).getByText("190")).toBeInTheDocument();
    expect(within(total).getByText("Building Blocks")).toBeInTheDocument();
    expect(
      within(total).getByText(
        "You have a strong foundation but may need to focus on specific weaknesses.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("If scoring low, streamline channels.")).toBeInTheDocument();
    expect(screen.getByText(/answers from 3 people/)).toBeInTheDocument();
  });
});
