import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ExplanationOut } from "@/lib/api/types";
import { errorResponse, fakeAssessment, fakeMe, fakeQuestionSet, stubApi } from "@/test/api";
import { renderWithMe } from "@/test/me";

import { POLL_MS, QuestionExplanation } from "./QuestionExplanation";
import { QuestionnairePage } from "./QuestionnairePage";

vi.mock("next/navigation", async () => (await import("@/test/navigation")).navigationMock());

const PATH = "/api/v1/readiness/questions/customer_journey_2/explanation";

function fakeExplanation(overrides: Partial<ExplanationOut> = {}): ExplanationOut {
  return {
    question_id: "customer_journey_2",
    question_set_version: 1,
    dimension_key: "customer_journey",
    dimension_name: "Customer Journey",
    status: "ready",
    explanation: [
      "This question asks whether feedback shapes the experience.",
      "It should happen regularly.",
    ],
    example: "A grocer changes its shelf signs after reading reviews.",
    sample: false,
    created_at: "2026-10-24T10:00:00Z",
    ...overrides,
  };
}

afterEach(() => {
  vi.useRealTimers();
});

describe("QuestionExplanation", () => {
  it("asks once, shows the plain explanation and names its dimension", async () => {
    const calls = stubApi({ [`POST ${PATH}`]: fakeExplanation() });
    const user = userEvent.setup();
    render(<QuestionExplanation questionId="customer_journey_2" version={1} />);

    const toggle = screen.getByRole("button", { name: "What does this mean?" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await user.click(toggle);

    expect(
      await screen.findByText(
        "This question asks whether feedback shapes the experience. It should happen regularly.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("A grocer changes its shelf signs after reading reviews.")).toBeVisible();
    expect(screen.getByText(/Written by AI about Customer Journey/)).toBeInTheDocument();
    expect(calls).toHaveLength(1);
    expect(calls[0]).toMatchObject({ method: "POST", path: PATH });

    // Hiding and showing again does not ask again.
    await user.click(screen.getByRole("button", { name: "Hide the explanation" }));
    await user.click(screen.getByRole("button", { name: "What does this mean?" }));
    expect(screen.getByText(/Written by AI/)).toBeInTheDocument();
    expect(calls).toHaveLength(1);
  });

  it("waits for a pending explanation by polling", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const calls = stubApi({
      [`POST ${PATH}`]: fakeExplanation({ status: "pending", explanation: null, example: null }),
      [`GET ${PATH}`]: fakeExplanation(),
    });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<QuestionExplanation questionId="customer_journey_2" version={1} />);

    await user.click(screen.getByRole("button", { name: "What does this mean?" }));
    expect(await screen.findByText("Writing a plain explanation...")).toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_MS);
    });

    expect(await screen.findByText(/Written by AI/)).toBeInTheDocument();
    expect(calls.map((c) => c.method)).toEqual(["POST", "GET"]);
  });

  it("offers to try again when the explanation failed", async () => {
    let asked = 0;
    stubApi({
      [`POST ${PATH}`]: () => {
        asked += 1;
        return asked === 1
          ? fakeExplanation({ status: "failed", explanation: null, example: null })
          : fakeExplanation();
      },
    });
    const user = userEvent.setup();
    render(<QuestionExplanation questionId="customer_journey_2" version={1} />);

    await user.click(screen.getByRole("button", { name: "What does this mean?" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We could not explain this question right now.",
    );
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText(/Written by AI/)).toBeInTheDocument();
  });

  it("shows the server's message, such as the daily limit", async () => {
    stubApi({
      [`POST ${PATH}`]: errorResponse(
        "too_many_requests",
        "Your organisation has asked for 150 explanations in the last day, the most allowed. Try again in about 3 hours.",
        429,
      ),
    });
    const user = userEvent.setup();
    render(<QuestionExplanation questionId="customer_journey_2" version={1} />);

    await user.click(screen.getByRole("button", { name: "What does this mean?" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Try again in about 3 hours.");
  });

  it("marks sample text while the AI is not connected", async () => {
    stubApi({ [`POST ${PATH}`]: fakeExplanation({ sample: true }) });
    const user = userEvent.setup();
    render(<QuestionExplanation questionId="customer_journey_2" version={1} />);

    await user.click(screen.getByRole("button", { name: "What does this mean?" }));
    expect(
      await screen.findByText("Sample text: the AI is not connected yet."),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Written by AI/)).not.toBeInTheDocument();
  });
});

describe("QuestionnairePage explanations", () => {
  const A = "/api/v1/readiness/assessments/77777777-7777-7777-7777-777777777777";

  it("offers an explanation under every question to people who answer", async () => {
    stubApi({
      [`GET ${A}`]: fakeAssessment(),
      "GET /api/v1/readiness/question-set": fakeQuestionSet(),
    });
    renderWithMe(
      <QuestionnairePage assessmentId="77777777-7777-7777-7777-777777777777" />,
      fakeMe(),
    );
    expect(
      await screen.findAllByRole("button", { name: "What does this mean?" }),
    ).toHaveLength(4);
  });

  it("offers none to people who only watch", async () => {
    stubApi({
      [`GET ${A}`]: fakeAssessment({ can_answer: false, my_answers: null }),
      "GET /api/v1/readiness/question-set": fakeQuestionSet(),
    });
    renderWithMe(
      <QuestionnairePage assessmentId="77777777-7777-7777-7777-777777777777" />,
      fakeMe(),
    );
    expect(await screen.findByText("Is feedback integrated?")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "What does this mean?" })).not.toBeInTheDocument();
  });
});
