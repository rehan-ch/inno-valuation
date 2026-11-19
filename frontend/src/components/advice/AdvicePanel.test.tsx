import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { errorResponse, fakeAdvice, fakeMe, fakeNoAdvice, stubApi } from "@/test/api";
import { renderWithMe } from "@/test/me";

import { AdvicePanel } from "./AdvicePanel";

vi.mock("next/navigation", async () => (await import("@/test/navigation")).navigationMock());

const ID = "55555555-5555-5555-5555-555555555555";
const PATH = `/api/v1/readiness/assessments/${ID}/advice`;
const REF = { kind: "readiness", assessmentId: ID } as const;
const NAMES = ["interpretation", "gap_actions", "recommendations", "consultation"] as const;
const FIXED = "TEST FIXTURE: the method's next steps would be here.";

function allPending() {
  const pending = fakeNoAdvice();
  for (const name of NAMES) pending[name] = { ...pending[name], status: "pending" } as never;
  return pending;
}

/** Advice on screen, with the gap actions still on their way. */
function actionsPending() {
  const waiting = fakeAdvice();
  waiting.gap_actions = { ...fakeNoAdvice().gap_actions, status: "pending" } as never;
  return waiting;
}

function part(name: string) {
  return within(screen.getByRole("region", { name }));
}

afterEach(() => {
  vi.useRealTimers();
});

describe("AdvicePanel", () => {
  it("shows each part as the AI's, with its dimension, and the method's text apart", async () => {
    stubApi({ [`GET ${PATH}`]: fakeAdvice() });
    renderWithMe(<AdvicePanel adviceRef={REF} />, fakeMe());

    await screen.findByText("What this result means");
    const meaning = part("What this result means");
    expect(meaning.getByText("The result shows a sound base. A few areas need steady work.")).toBeInTheDocument();
    expect(meaning.getByText("Proposed by AI")).toBeInTheDocument();
    expect(meaning.getByText("Agility is among the lowest areas.")).toBeInTheDocument();
    expect(meaning.getByRole("link", { name: "Organizational Agility" })).toHaveAttribute(
      "href",
      "/dimensions/organizational_agility",
    );

    const recommendations = part("Recommendations for the priorities");
    expect(recommendations.getByRole("link", { name: "Organizational Agility" })).toBeInTheDocument();
    // The fixed next steps are labelled as the method's, apart from the AI's advice: the AI
    // mark sits on the AI's own block, not on the heading that covers both.
    const fixed = recommendations.getByText(FIXED);
    expect(fixed.previousElementSibling).toHaveTextContent("Next steps from the method, as written");
    const mark = recommendations.getByText("Proposed by AI");
    expect(mark.previousElementSibling).toHaveTextContent("The AI's advice");
    expect(within(fixed.parentElement as HTMLElement).queryByText("Proposed by AI")).not.toBeInTheDocument();
    expect(
      within(recommendations.getByRole("heading", { name: "Recommendations for the priorities" }).parentElement as HTMLElement)
        .queryByText("Proposed by AI"),
    ).not.toBeInTheDocument();
    expect(recommendations.getByText(/The method's next steps are shown as written/)).toBeInTheDocument();
    expect(recommendations.getByText("Run a short review of how decisions are made.")).toBeInTheDocument();
    expect(recommendations.getByText("Time from decision to action.")).toBeInTheDocument();

    const actions = part("Actions to close the gaps");
    expect(actions.getByText("Name one owner for agility.")).toBeInTheDocument();

    const consultation = part("Consultation");
    expect(consultation.getByText("Several areas sit well below where you want them.")).toBeInTheDocument();
    expect(consultation.getByText("Agility is well short of its target.")).toBeInTheDocument();

    // Usage figures are not shown unless the API sends them.
    expect(screen.queryByText(/Usage \(platform admins only\)/)).not.toBeInTheDocument();
    expect(screen.getAllByText(/It can be wrong, so use your own judgement/)).toHaveLength(4);
  });

  it("asks for everything once, waits by polling and then shows the advice", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const pending = allPending();
    let reads = 0;
    const calls = stubApi({
      [`GET ${PATH}`]: () => (reads++ === 0 ? fakeNoAdvice() : fakeAdvice()),
      [`POST ${PATH}`]: pending,
    });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderWithMe(<AdvicePanel adviceRef={REF} />, fakeMe());

    await user.click(await screen.findByRole("button", { name: "Get AI advice" }));
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ parts: null, regenerate: false });
    expect(await screen.findByText("Putting the result into words...")).toBeInTheDocument();
    // Nothing can be asked again while it is on its way.
    expect(screen.queryByRole("button", { name: /Ask/ })).not.toBeInTheDocument();

    await vi.advanceTimersByTimeAsync(2100);
    expect(await screen.findByText("Agility is among the lowest areas.")).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "GET")).toHaveLength(2);
    // A screen reader hears that the wait is over.
    expect(screen.getByText("The AI has finished. Its advice is on the page.")).toHaveAttribute(
      "aria-live",
      "polite",
    );
  });

  it("stops asking the server once the page is left", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let reads = 0;
    const calls = stubApi({
      [`GET ${PATH}`]: () => (reads++ === 0 ? fakeNoAdvice() : allPending()),
      [`POST ${PATH}`]: allPending(),
    });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const { unmount } = renderWithMe(<AdvicePanel adviceRef={REF} />, fakeMe());
    await user.click(await screen.findByRole("button", { name: "Get AI advice" }));
    await screen.findByText("Putting the result into words...");
    await vi.advanceTimersByTimeAsync(2100);

    unmount();
    const before = calls.filter((c) => c.method === "GET").length;
    await vi.advanceTimersByTimeAsync(20_000);
    expect(calls.filter((c) => c.method === "GET")).toHaveLength(before);
  });

  it("keeps waiting for a pending part when another ask is refused", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let done = false;
    stubApi({
      [`GET ${PATH}`]: () => (done ? fakeAdvice() : actionsPending()),
      [`POST ${PATH}`]: () => errorResponse("too_many_requests", "Too often today.", 429),
    });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderWithMe(<AdvicePanel adviceRef={REF} />, fakeMe());

    await screen.findByText("Working out actions...");
    await user.click(part("What this result means").getByRole("button", { name: /^Ask again/ }));
    expect(await screen.findByText("Too often today.")).toBeInTheDocument();

    done = true;
    await vi.advanceTimersByTimeAsync(4100);
    expect(await screen.findByText("Name one owner for agility.")).toBeInTheDocument();
    expect(screen.queryByText("Working out actions...")).not.toBeInTheDocument();
  });

  it("keeps the advice on screen and keeps waiting when one check fails", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let reads = 0;
    stubApi({
      [`GET ${PATH}`]: () => {
        reads += 1;
        if (reads === 2) return errorResponse("server_error", "Something broke.", 500);
        return reads === 1 ? actionsPending() : fakeAdvice();
      },
    });
    renderWithMe(<AdvicePanel adviceRef={REF} />, fakeMe());

    await screen.findByText("Working out actions...");
    await vi.advanceTimersByTimeAsync(2100);
    expect(screen.getByText(/The result shows a sound base/)).toBeInTheDocument();
    expect(screen.queryByText("Something broke.")).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();

    await vi.advanceTimersByTimeAsync(2100);
    expect(await screen.findByText("Name one owner for agility.")).toBeInTheDocument();
  });

  it("stops after several failed checks, keeps the advice and offers to check again", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let broken = true;
    let reads = 0;
    const calls = stubApi({
      [`GET ${PATH}`]: () => {
        reads += 1;
        if (reads === 1) return actionsPending();
        return broken ? errorResponse("server_error", "Something broke.", 500) : fakeAdvice();
      },
    });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderWithMe(<AdvicePanel adviceRef={REF} />, fakeMe());

    await screen.findByText("Working out actions...");
    await vi.advanceTimersByTimeAsync(20_000);
    expect(calls).toHaveLength(4); // the first read and three failed checks, then no more
    const checkAgain = await screen.findByRole("button", { name: "Check again" });
    expect(screen.getByText(/The result shows a sound base/)).toBeInTheDocument();
    expect(screen.queryByText("Working out actions...")).not.toBeInTheDocument();

    broken = false;
    await user.click(checkAgain);
    expect(await screen.findByText("Name one owner for agility.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Check again" })).not.toBeInTheDocument();
  });

  it("stops waiting after five minutes without leaving a spinner, and checks again when asked", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let failedNow = false;
    const failed = fakeNoAdvice();
    for (const name of NAMES) failed[name] = { ...failed[name], status: "failed" } as never;
    const calls = stubApi({ [`GET ${PATH}`]: () => (failedNow ? failed : allPending()) });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderWithMe(<AdvicePanel adviceRef={REF} />, fakeMe());

    await screen.findByText("Putting the result into words...");
    await vi.advanceTimersByTimeAsync(5 * 60_000 + 5_000);
    const atGiveUp = calls.length;
    await vi.advanceTimersByTimeAsync(60_000);
    expect(calls).toHaveLength(atGiveUp);
    expect(await screen.findByText(/This is taking longer than usual/)).toBeInTheDocument();
    expect(screen.queryByText("Putting the result into words...")).not.toBeInTheDocument();

    // The server has since given the lost runs up: checking again shows it at once.
    failedNow = true;
    await user.click(screen.getByRole("button", { name: "Check again" }));
    expect(await part("Consultation").findByText("The AI could not write this right now.")).toBeInTheDocument();
    expect(calls).toHaveLength(atGiveUp + 1);
    expect(screen.queryByRole("button", { name: "Check again" })).not.toBeInTheDocument();
    expect(part("Consultation").getByRole("button", { name: "Try again: Consultation" })).toBeInTheDocument();
  });

  it("asks again for one part only", async () => {
    const calls = stubApi({ [`GET ${PATH}`]: fakeAdvice(), [`POST ${PATH}`]: fakeAdvice() });
    const user = userEvent.setup();
    renderWithMe(<AdvicePanel adviceRef={REF} />, fakeMe());

    await screen.findByText("What this result means");
    // Four buttons read "Ask again"; each one's name says which part it asks for.
    expect(screen.getAllByRole("button", { name: /^Ask again: / })).toHaveLength(4);
    await user.click(
      part("Actions to close the gaps").getByRole("button", { name: "Ask again: Actions to close the gaps" }),
    );
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({
      parts: ["gap_actions"],
      regenerate: true,
    });
  });

  it("gives a reader who may not ask no way to ask", async () => {
    stubApi({ [`GET ${PATH}`]: fakeAdvice({ can_request: false }) });
    const { unmount } = renderWithMe(<AdvicePanel adviceRef={REF} />, fakeMe());
    await screen.findByText("What this result means");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    unmount();

    stubApi({ [`GET ${PATH}`]: fakeNoAdvice({ can_request: false }) });
    renderWithMe(<AdvicePanel adviceRef={REF} />, fakeMe());
    expect(await screen.findByText(/Nobody has asked for advice on this result yet/)).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("says when text is a sample, out of date, or could not be refreshed", async () => {
    const advice = fakeAdvice();
    advice.interpretation = { ...advice.interpretation, sample: true };
    advice.gap_actions = { ...advice.gap_actions, outdated: true };
    advice.recommendations = { ...advice.recommendations, status: "failed" };
    advice.consultation = {
      ...advice.consultation,
      status: "failed",
      generated_at: null,
      suggest: false,
      message: [],
      reasons: [],
    };
    stubApi({ [`GET ${PATH}`]: advice });
    renderWithMe(<AdvicePanel adviceRef={REF} />, fakeMe());

    await screen.findByText("What this result means");
    expect(part("What this result means").getByText("Sample text")).toBeInTheDocument();
    expect(part("What this result means").queryByText("Proposed by AI")).not.toBeInTheDocument();
    expect(
      part("Actions to close the gaps").getByText(
        /This was written before something it is based on changed. Ask again to bring it up to date./,
      ),
    ).toBeInTheDocument();
    const recommendations = part("Recommendations for the priorities");
    expect(recommendations.getByText(/The earlier text is still shown/)).toBeInTheDocument();
    expect(recommendations.getByText(FIXED)).toBeInTheDocument();
    const consultation = part("Consultation");
    expect(consultation.getByText("The AI could not write this right now.")).toBeInTheDocument();
    expect(consultation.getByRole("button", { name: "Try again: Consultation" })).toBeInTheDocument();
  });

  it("shows usage figures when the API sends them, and a part switched off not at all", async () => {
    const advice = fakeAdvice();
    advice.interpretation = {
      ...advice.interpretation,
      usage: { model: "claude-sonnet-5-5", input_tokens: 1200, output_tokens: 300, cost_usd: "0.0054" },
    };
    advice.consultation = { ...fakeNoAdvice().consultation, status: "off" };
    stubApi({ [`GET ${PATH}`]: advice });
    renderWithMe(<AdvicePanel adviceRef={REF} />, fakeMe());

    expect(
      await screen.findByText(/claude-sonnet-5-5 · 1,200 tokens in · 300 out · US\$0.0054/),
    ).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Consultation" })).not.toBeInTheDocument();
  });

  it("shows the server's message when asking is refused", async () => {
    stubApi({
      [`GET ${PATH}`]: fakeNoAdvice(),
      [`POST ${PATH}`]: errorResponse(
        "too_many_requests",
        "Your organisation has asked for AI advice as often as is allowed in one day.",
        429,
      ),
    });
    const user = userEvent.setup();
    renderWithMe(<AdvicePanel adviceRef={REF} />, fakeMe());
    await user.click(await screen.findByRole("button", { name: "Get AI advice" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("as often as is allowed in one day");
    expect(screen.getByRole("button", { name: "Get AI advice" })).toBeEnabled();
  });
});
