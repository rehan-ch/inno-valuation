import { screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  IDEA_ID,
  IQ_ASSESSMENT_ID,
  errorResponse,
  fakeAdvice,
  fakeDimensionDetail,
  fakeMe,
  fakeNoAdvice,
  stubApi,
} from "@/test/api";
import { renderWithMe } from "@/test/me";
import { routerReplace, setLocation } from "@/test/navigation";

import { DimensionPage } from "./DimensionPage";

vi.mock("next/navigation", async () => (await import("@/test/navigation")).navigationMock());

const PATH = "/api/v1/dashboard/dimensions/organizational_agility";

const ADVICE = {
  "GET /api/v1/readiness/assessments/55555555-5555-5555-5555-555555555555/advice": fakeAdvice(),
  [`GET /api/v1/ideas/${IDEA_ID}/assessments/${IQ_ASSESSMENT_ID}/advice`]: fakeNoAdvice({
    subject: "iq_assessment",
  }),
};

function card(title: string): HTMLElement {
  return screen.getByRole("heading", { name: title }).closest("section") as HTMLElement;
}

describe("DimensionPage", () => {
  it("shows the book's text and the two scores apart, each with target, gap and trend", async () => {
    setLocation(`/dimensions/organizational_agility?idea=${IDEA_ID}`);
    const calls = stubApi({ [`GET ${PATH}`]: fakeDimensionDetail(), ...ADVICE });
    renderWithMe(<DimensionPage dimensionKey="organizational_agility" />, fakeMe());

    expect(await screen.findByRole("heading", { name: "7. Organizational Agility" })).toBeInTheDocument();
    expect(calls[0]?.path).toBe(PATH);
    expect(screen.getByText("Process Innovation")).toBeInTheDocument();
    expect(screen.getByText("How quickly the organisation adapts.")).toBeInTheDocument();
    expect(screen.getByText("Decision speed")).toBeInTheDocument();

    // The fixed next-step text, exactly as sent.
    expect(within(card("Next steps from the method")).getByText("Adopt agile ways of working.")).toBeInTheDocument();
    // The AI's advice about this dimension, for each result apart, marked as the AI's.
    const forReadiness = within(await screen.findByRole("region", { name: "For the readiness result" }));
    expect(await forReadiness.findByText("Agility is among the lowest areas.")).toBeInTheDocument();
    // Each of the AI's blocks carries the mark; the method's next steps beside them do not.
    expect(forReadiness.getAllByText("Proposed by AI")).toHaveLength(3);
    const fixed = forReadiness.getByText("TEST FIXTURE: the method's next steps would be here.");
    expect(fixed.previousElementSibling).toHaveTextContent("Next steps from the method, as written");
    expect(within(fixed.parentElement as HTMLElement).queryByText("Proposed by AI")).not.toBeInTheDocument();
    expect(forReadiness.queryByText(/written before something it is based on changed/)).not.toBeInTheDocument();
    expect(forReadiness.getByText("Name one owner for agility.")).toBeInTheDocument();
    expect(forReadiness.getByText("Run a short review of how decisions are made.")).toBeInTheDocument();
    expect(forReadiness.getByText("Agility is well short of its target.")).toBeInTheDocument();
    // Advice about other dimensions stays on the result page.
    expect(forReadiness.queryByText(/customer journey is in a workable place/)).not.toBeInTheDocument();
    expect(forReadiness.getByRole("link", { name: "Full advice, and ask again" })).toHaveAttribute(
      "href",
      "/readiness/55555555-5555-5555-5555-555555555555/result",
    );
    const forIdea = within(screen.getByRole("region", { name: /^For the idea/ }));
    expect(await forIdea.findByRole("button", { name: "Get AI advice" })).toBeInTheDocument();

    const readiness = within(card("Readiness"));
    expect(readiness.getAllByText("15")).toHaveLength(2); // the headline and the trend row
    expect(readiness.getByText("Priority 5")).toBeInTheDocument();
    expect(readiness.getByText(/5 below target/)).toBeInTheDocument();
    expect(readiness.getByText("We adapt quickly to change.")).toBeInTheDocument();
    const earlier = readiness.getByRole("link", { name: "Sep 1, 2026" });
    expect(earlier).toHaveAttribute("href", "/readiness/66666666-6666-6666-6666-666666666666/result");
    expect(readiness.getByText("+2")).toBeInTheDocument();

    const iq = within(card("Idea score"));
    expect(iq.getByText("5")).toBeInTheDocument();
    expect(iq.getByText("Innovation")).toBeInTheDocument();
    expect(iq.getByText("Novel.")).toBeInTheDocument();
    expect(iq.getByText("The AI proposed 4; the owner set 5")).toBeInTheDocument();
    expect(iq.getByText("The team has reorganised twice this year.")).toBeInTheDocument();
    expect(iq.getByText(/3 below target/)).toBeInTheDocument();
    // Neither card carries the other scale's figure.
    expect(readiness.queryByText("Innovation")).not.toBeInTheDocument();

    // Neighbours keep the selected idea.
    expect(screen.getByRole("link", { name: /Collaborative Synergy/ })).toHaveAttribute(
      "href",
      `/dimensions/collaborative_synergy?idea=${IDEA_ID}`,
    );
  });

  it("drops the other organisation's idea and loads again when the organisation is switched", async () => {
    setLocation(`/dimensions/organizational_agility?idea=${IDEA_ID}`);
    routerReplace.mockClear();
    const calls = stubApi({ [`GET ${PATH}`]: fakeDimensionDetail(), ...ADVICE });
    const { setMe } = renderWithMe(<DimensionPage dimensionKey="organizational_agility" />, fakeMe());
    await screen.findByRole("heading", { name: "7. Organizational Agility" });

    setMe(fakeMe({ active_organisation_id: "33333333-3333-3333-3333-333333333333" }));
    expect(routerReplace).toHaveBeenCalledWith("/dimensions/organizational_agility");

    // Without an idea in the address, the switch simply loads the new organisation's page.
    setLocation("/dimensions/organizational_agility");
    setMe(fakeMe({ active_organisation_id: "44444444-4444-4444-4444-444444444444" }));
    await screen.findByRole("heading", { name: "7. Organizational Agility" });
    expect(calls.filter((c) => c.path === PATH)).toHaveLength(2);
  });

  it("says so when the AI could not write its advice", async () => {
    setLocation("/dimensions/organizational_agility");
    const failed = fakeNoAdvice();
    failed.interpretation = { ...failed.interpretation, status: "failed" };
    stubApi({
      [`GET ${PATH}`]: fakeDimensionDetail({ iq: null, ideas: [] }),
      "GET /api/v1/readiness/assessments/55555555-5555-5555-5555-555555555555/advice": failed,
    });
    renderWithMe(<DimensionPage dimensionKey="organizational_agility" />, fakeMe());

    const advice = within(await screen.findByRole("region", { name: "For the readiness result" }));
    expect(await advice.findByText(/The AI could not write its advice right now/)).toBeInTheDocument();
    expect(advice.getByRole("link", { name: "Open the result to try again" })).toHaveAttribute(
      "href",
      "/readiness/55555555-5555-5555-5555-555555555555/result",
    );
    expect(advice.queryByRole("button", { name: "Get AI advice" })).not.toBeInTheDocument();
  });

  it("says when the advice shown for the dimension is out of date", async () => {
    setLocation(`/dimensions/organizational_agility?idea=${IDEA_ID}`);
    const advice = fakeAdvice();
    advice.gap_actions = { ...advice.gap_actions, outdated: true };
    stubApi({
      [`GET ${PATH}`]: fakeDimensionDetail(),
      ...ADVICE,
      "GET /api/v1/readiness/assessments/55555555-5555-5555-5555-555555555555/advice": advice,
    });
    renderWithMe(<DimensionPage dimensionKey="organizational_agility" />, fakeMe());

    const forReadiness = within(await screen.findByRole("region", { name: "For the readiness result" }));
    expect(
      await forReadiness.findByText(/This was written before something it is based on changed/),
    ).toBeInTheDocument();
    expect(forReadiness.getByRole("link", { name: "Open the result to ask again" })).toHaveAttribute(
      "href",
      "/readiness/55555555-5555-5555-5555-555555555555/result",
    );
  });

  it("says what is missing when there is no result on either scale", async () => {
    setLocation("/dimensions/organizational_agility");
    stubApi({ [`GET ${PATH}`]: fakeDimensionDetail({ readiness: null, iq: null, ideas: [] }) });
    renderWithMe(<DimensionPage dimensionKey="organizational_agility" />, fakeMe());

    expect(await screen.findByText(/no final readiness result yet/)).toBeInTheDocument();
    expect(screen.getByText(/No idea has confirmed scores yet/)).toBeInTheDocument();
    expect(screen.getByText("Adopt agile ways of working.")).toBeInTheDocument();
  });

  it("explains an unknown dimension instead of failing", async () => {
    setLocation("/dimensions/nope");
    stubApi({ "GET /api/v1/dashboard/dimensions/nope": errorResponse("not_found", "Not found.", 404) });
    renderWithMe(<DimensionPage dimensionKey="nope" />, fakeMe());

    expect(await screen.findByText("This dimension or idea could not be found.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to the dashboard" })).toHaveAttribute("href", "/dashboard");
  });
});
