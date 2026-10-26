import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { setUnauthorizedHandler } from "@/lib/api/client";
import type { ConsensusOut, ResultOut } from "@/lib/api/types";
import {
  errorResponse,
  fakeAssessment,
  fakeAssessmentSummary,
  fakeMe,
  fakeQuestionSet,
  stubApi,
} from "@/test/api";
import type { RecordedCall } from "@/test/api";
import { renderWithMe } from "@/test/me";
import { routerPush, routerReplace } from "@/test/navigation";

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

  it("reloads the list, from a loading state, after a switch in the header", async () => {
    const BETA = "99999999-9999-9999-9999-999999999999";
    let releaseLoad: () => void = () => {};
    let loads = 0;
    stubApi({
      "GET /api/v1/readiness/assessments": () => {
        loads += 1;
        return loads === 1
          ? [fakeAssessmentSummary({ status: "collecting", created_by_name: "Olive Owner" })]
          : new Promise((resolve) => {
              releaseLoad = () => resolve([]);
            });
      },
    });
    const me = fakeMe({
      memberships: [
        ...fakeMe().memberships,
        {
          organisation_id: BETA,
          organisation_name: "Beta Ltd",
          organisation_status: "active",
          role: "owner",
        },
      ],
    });

    const { setMe } = renderWithMe(<ReadinessListPage />, me);
    expect(await screen.findByText(/by Olive Owner/)).toBeInTheDocument();
    // An open assessment means no Start card.
    expect(screen.queryByRole("button", { name: "Start a readiness assessment" })).not.toBeInTheDocument();

    setMe({ ...me, active_organisation_id: BETA });

    // The old organisation's assessment is gone while the new list loads.
    expect(await screen.findByText("Loading assessments...")).toBeInTheDocument();
    expect(screen.queryByText(/by Olive Owner/)).not.toBeInTheDocument();
    releaseLoad();
    expect(await screen.findByText("No assessment yet.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start a readiness assessment" })).toBeInTheDocument();
  });
});

describe("QuestionnairePage", () => {
  afterEach(() => setUnauthorizedHandler(null));

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
          { user_id: "u1", name: "Mia Member", answered: 4, submitted_at: "2026-10-21T09:00:00Z" },
          { user_id: "u2", name: "Late Larry", answered: 1, submitted_at: null },
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

  it("undoes an answer whose save failed, so it is neither shown nor counted", async () => {
    stubApi({
      [`GET ${A}`]: fakeAssessment(),
      "GET /api/v1/readiness/question-set": fakeQuestionSet(),
      [`PATCH ${A}/my-answers`]: errorResponse("wrong_status", "Answers are closed.", 409),
    });
    const user = userEvent.setup();

    renderWithMe(<QuestionnairePage assessmentId={ID} />, fakeMe());
    const question = await screen.findByRole("group", {
      name: "Do you understand the end-to-end experience?",
    });
    await user.click(within(question).getByRole("radio", { name: "4" }));

    expect(await screen.findByRole("status", { name: "Save status" })).toHaveTextContent(
      /Not saved/,
    );
    expect(within(question).getByRole("radio", { name: "4" })).not.toBeChecked();
    expect(screen.getByText("0 of 4 answered")).toBeInTheDocument();
  });

  it("submits only after the last answer has saved", async () => {
    let releaseSave: () => void = () => {};
    const order: string[] = [];
    stubApi({
      [`GET ${A}`]: fakeAssessment({
        my_answers: { customer_journey_1: 3, customer_journey_2: 4, brand_magnetism_1: 3 },
      }),
      "GET /api/v1/readiness/question-set": fakeQuestionSet(),
      [`PATCH ${A}/my-answers`]: () =>
        new Promise((resolve) => {
          releaseSave = () => {
            order.push("save");
            resolve(fakeAssessment({ my_answers: ALL }));
          };
        }),
      [`POST ${A}/my-answers/submit`]: () => {
        order.push("submit");
        return fakeAssessment({ my_answers: ALL, my_submitted_at: "2026-10-21T10:00:00Z" });
      },
    });
    const user = userEvent.setup();

    renderWithMe(<QuestionnairePage assessmentId={ID} />, fakeMe());
    const last = await screen.findByRole("group", { name: "Does the story resonate?" });
    await user.click(within(last).getByRole("radio", { name: "2" }));
    // The last answer is still saving when the person submits.
    await user.click(screen.getByRole("button", { name: "Submit my answers" }));
    await user.click(screen.getByRole("button", { name: "Submit now" }));
    expect(order).toEqual([]);
    releaseSave();

    expect(await screen.findByText(/Your answers are submitted/)).toBeInTheDocument();
    expect(order).toEqual(["save", "submit"]);
  });

  it("keeps a failed answer marked after a later save works", async () => {
    let saves = 0;
    stubApi({
      [`GET ${A}`]: fakeAssessment(),
      "GET /api/v1/readiness/question-set": fakeQuestionSet(),
      [`PATCH ${A}/my-answers`]: (call: RecordedCall) => {
        saves += 1;
        return saves === 1
          ? errorResponse("unknown_error", "The server returned an error (500).", 500)
          : fakeAssessment({
              my_answers: (call.body as { answers: Record<string, number> }).answers,
            });
      },
    });
    const user = userEvent.setup();

    renderWithMe(<QuestionnairePage assessmentId={ID} />, fakeMe());
    const first = await screen.findByRole("group", {
      name: "Do you understand the end-to-end experience?",
    });
    const second = screen.getByRole("group", { name: "Is feedback integrated?" });
    await user.click(within(first).getByRole("radio", { name: "4" }));
    expect(await screen.findByRole("status", { name: "Save status" })).toHaveTextContent(
      /Not saved/,
    );
    await user.click(within(second).getByRole("radio", { name: "3" }));

    expect(await screen.findByRole("status", { name: "Save status" })).toHaveTextContent(
      "Saved, but 1 answer was not saved. Choose again where marked.",
    );
    expect(within(first).getByText("Not saved. Choose your answer again.")).toBeInTheDocument();
    expect(within(second).queryByText(/Not saved/)).not.toBeInTheDocument();
    expect(screen.getByText("1 of 4 answered")).toBeInTheDocument();

    // Choosing the marked question again clears the mark once the save works.
    await user.click(within(first).getByRole("radio", { name: "5, Strongly Agree" }));
    expect(await screen.findByText("Saved")).toBeInTheDocument();
    expect(within(first).queryByText(/Not saved/)).not.toBeInTheDocument();
  });

  it("says a 403 is about permission, not the connection", async () => {
    stubApi({
      [`GET ${A}`]: fakeAssessment(),
      "GET /api/v1/readiness/question-set": fakeQuestionSet(),
      [`PATCH ${A}/my-answers`]: errorResponse("forbidden", "Not allowed.", 403),
    });
    const user = userEvent.setup();

    renderWithMe(<QuestionnairePage assessmentId={ID} />, fakeMe());
    const question = await screen.findByRole("group", {
      name: "Do you understand the end-to-end experience?",
    });
    await user.click(within(question).getByRole("radio", { name: "4" }));

    const status = await screen.findByRole("status", { name: "Save status" });
    await vi.waitFor(() => expect(status).toHaveTextContent(/Not saved/));
    expect(status).toHaveTextContent("You do not have permission to change this.");
    expect(status).not.toHaveTextContent(/connection/);
  });

  it("hands a 401 from a save to the registered handler", async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    stubApi({
      [`GET ${A}`]: fakeAssessment(),
      "GET /api/v1/readiness/question-set": fakeQuestionSet(),
      [`PATCH ${A}/my-answers`]: errorResponse("not_authenticated", "Please sign in.", 401),
    });
    const user = userEvent.setup();

    renderWithMe(<QuestionnairePage assessmentId={ID} />, fakeMe());
    const question = await screen.findByRole("group", {
      name: "Do you understand the end-to-end experience?",
    });
    await user.click(within(question).getByRole("radio", { name: "4" }));

    await vi.waitFor(() => expect(handler).toHaveBeenCalledTimes(1));
    expect(await screen.findByRole("status", { name: "Save status" })).toHaveTextContent(
      /session has ended/,
    );
  });

  it("locks the answers while the submit runs", async () => {
    let releaseSubmit: () => void = () => {};
    stubApi({
      [`GET ${A}`]: fakeAssessment({ my_answers: ALL, my_status: "in_progress" }),
      "GET /api/v1/readiness/question-set": fakeQuestionSet(),
      [`POST ${A}/my-answers/submit`]: () =>
        new Promise((resolve) => {
          releaseSubmit = () =>
            resolve(
              fakeAssessment({
                my_answers: ALL,
                my_status: "submitted",
                my_submitted_at: "2026-10-21T10:00:00Z",
              }),
            );
        }),
    });
    const user = userEvent.setup();

    renderWithMe(<QuestionnairePage assessmentId={ID} />, fakeMe());
    const question = await screen.findByRole("group", { name: "Is feedback integrated?" });
    expect(within(question).getByRole("radio", { name: "4" })).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "Submit my answers" }));
    await user.click(screen.getByRole("button", { name: "Submit now" }));

    expect(within(question).getByRole("radio", { name: "4" })).toBeDisabled();
    releaseSubmit();

    expect(await screen.findByText(/Your answers are submitted/)).toBeInTheDocument();
    expect(within(question).getByRole("radio", { name: "4" })).toBeDisabled();
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
    answers: answers.map((answer, i) => ({
      user_id: `u${i}`,
      name: ["Olive", "Mia"][i] ?? "X",
      answer,
    })),
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

  it("saves a note when its field loses focus", async () => {
    const calls = stubApi({
      [`GET ${A}`]: fakeAssessment({ status: "consensus" }),
      [`GET ${A}/consensus`]: fakeConsensus(),
      "GET /api/v1/readiness/question-set": fakeQuestionSet(),
      [`PATCH ${A}/consensus`]: fakeConsensus(),
    });
    const user = userEvent.setup();

    renderWithMe(<ConsensusPage assessmentId={ID} />, fakeMe());
    const question = await screen.findByRole("group", {
      name: "Do you understand the end-to-end experience?",
    });
    const row = question.closest("li") as HTMLElement;
    await user.type(within(row).getByLabelText("Note for this question"), "Agreed after a chat");
    expect(calls.filter((c) => c.method === "PATCH")).toHaveLength(0);
    await user.tab();

    expect(calls.at(-1)).toMatchObject({
      method: "PATCH",
      path: `${A}/consensus`,
      body: { answers: {}, notes: { customer_journey_1: "Agreed after a chat" } },
    });
    expect(await screen.findByText("Saved")).toBeInTheDocument();
  });

  it("goes to the result when the assessment is already final", async () => {
    routerReplace.mockClear();
    const calls = stubApi({
      [`GET ${A}`]: fakeAssessment({ status: "final", finalised_at: "2026-10-21T12:00:00Z" }),
    });

    renderWithMe(<ConsensusPage assessmentId={ID} />, fakeMe());

    await vi.waitFor(() => expect(routerReplace).toHaveBeenCalledWith(`/readiness/${ID}/result`));
    expect(calls.map((c) => c.path)).toEqual([A]);
  });

  it("keeps a failed change marked after a later save works", async () => {
    let saves = 0;
    stubApi({
      [`GET ${A}`]: fakeAssessment({ status: "consensus" }),
      [`GET ${A}/consensus`]: fakeConsensus(),
      "GET /api/v1/readiness/question-set": fakeQuestionSet(),
      [`PATCH ${A}/consensus`]: () => {
        saves += 1;
        return saves === 1
          ? errorResponse("unknown_error", "The server returned an error (500).", 500)
          : fakeConsensus({ customer_journey_2: 4 });
      },
    });
    const user = userEvent.setup();

    renderWithMe(<ConsensusPage assessmentId={ID} />, fakeMe());
    const first = await screen.findByRole("group", {
      name: "Do you understand the end-to-end experience?",
    });
    const second = screen.getByRole("group", { name: "Is feedback integrated?" });
    await user.click(within(first).getByRole("radio", { name: "Agreed answer 4" }));
    expect(await screen.findByRole("status", { name: "Save status" })).toHaveTextContent(
      /Not saved/,
    );
    await user.click(within(second).getByRole("radio", { name: "Agreed answer 4" }));

    expect(await screen.findByRole("status", { name: "Save status" })).toHaveTextContent(
      "Saved, but 1 change was not saved. Change again where marked.",
    );
    expect(
      within(first).getByText("Not saved. Set the agreed answer or note again."),
    ).toBeInTheDocument();
    expect(within(second).queryByText(/Not saved/)).not.toBeInTheDocument();
    expect(screen.getByText("1 of 4 agreed")).toBeInTheDocument();
  });

  it("says a 403 is about permission, not the connection", async () => {
    stubApi({
      [`GET ${A}`]: fakeAssessment({ status: "consensus" }),
      [`GET ${A}/consensus`]: fakeConsensus(),
      "GET /api/v1/readiness/question-set": fakeQuestionSet(),
      [`PATCH ${A}/consensus`]: errorResponse("forbidden", "Not allowed.", 403),
    });
    const user = userEvent.setup();

    renderWithMe(<ConsensusPage assessmentId={ID} />, fakeMe());
    const question = await screen.findByRole("group", {
      name: "Do you understand the end-to-end experience?",
    });
    await user.click(within(question).getByRole("radio", { name: "Agreed answer 4" }));

    const status = await screen.findByRole("status", { name: "Save status" });
    await vi.waitFor(() => expect(status).toHaveTextContent(/Not saved/));
    expect(status).toHaveTextContent("You do not have permission to change this.");
    expect(status).not.toHaveTextContent(/connection/);
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

  it("shows the permission message when the result is not for this person", async () => {
    stubApi({
      [`GET ${A}/result`]: errorResponse(
        "forbidden",
        "You do not have access to this organisation's results.",
        403,
      ),
    });

    renderWithMe(<ResultPage assessmentId={ID} />, fakeMe());

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "You do not have access to this organisation's results.",
    );
    expect(screen.queryByRole("region", { name: "Total" })).not.toBeInTheDocument();
  });
});
