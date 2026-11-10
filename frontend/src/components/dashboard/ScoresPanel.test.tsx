import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import {
  EMPTY_DASHBOARD,
  IDEA_ID,
  fakeAssessmentSummary,
  fakeDashboard,
  fakeIdeaSummary,
  fakeMe,
  fakeMember,
  fakeOrganisation,
  stubApi,
} from "@/test/api";
import { renderWithMe } from "@/test/me";

import { DashboardPage } from "./DashboardPage";

vi.mock("next/navigation", async () => (await import("@/test/navigation")).navigationMock());

const OTHER_IDEA = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";

function base(dashboard: unknown) {
  return {
    "GET /api/v1/organisation": fakeOrganisation({ role: "member" }),
    "GET /api/v1/organisation/members": [fakeMember()],
    "GET /api/v1/readiness/assessments": [fakeAssessmentSummary({ status: "final", total: 190 })],
    "GET /api/v1/ideas": [fakeIdeaSummary()],
    "GET /api/v1/dashboard": dashboard,
  };
}

function card(title: string): HTMLElement {
  return screen.getByRole("heading", { name: title }).closest("section") as HTMLElement;
}

describe("the dashboard's headline scores", () => {
  it("shows readiness out of 300 and the idea's IQ out of 100 as two separate cards", async () => {
    stubApi(base(fakeDashboard()));
    renderWithMe(<DashboardPage />, fakeMe());

    const readiness = within(await screen.findByRole("heading", { name: "Innovation Readiness" }).then(() => card("Innovation Readiness")));
    expect(readiness.getByText("190")).toBeInTheDocument();
    expect(readiness.getByText("/ 300")).toBeInTheDocument();
    expect(readiness.getByText("Building Blocks")).toBeInTheDocument();
    expect(
      readiness.getByText("You have a strong foundation but may need to focus on specific weaknesses."),
    ).toBeInTheDocument();
    expect(readiness.getByRole("link", { name: "See the result" })).toHaveAttribute(
      "href",
      "/readiness/55555555-5555-5555-5555-555555555555/result",
    );

    const iq = within(card("Innovation Quotient"));
    expect(iq.getByText("70.0")).toBeInTheDocument();
    expect(iq.getByText("/ 100")).toBeInTheDocument();
    expect(iq.getByText("IQ of Same-day delivery")).toBeInTheDocument();
    expect(iq.getByText("$714.29 per innovation point. Lower is better.")).toBeInTheDocument();
    expect(iq.getByRole("link", { name: "See the result" })).toHaveAttribute(
      "href",
      `/ideas/${IDEA_ID}/assessments/99999999-9999-9999-9999-999999999999`,
    );

    // Never a combined number: each figure lives in its own card and nowhere else do the
    // two meet (no 260, no average, no "overall").
    expect(readiness.queryByText("70.0")).not.toBeInTheDocument();
    expect(iq.queryByText("190")).not.toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/overall score|combined|260|130/i);
  });

  it("switches the compass and the priorities between readiness and the idea", async () => {
    stubApi(base(fakeDashboard()));
    const user = userEvent.setup();
    renderWithMe(<DashboardPage />, fakeMe());

    expect(await screen.findByRole("group", { name: /Readiness compass/ })).toBeInTheDocument();
    const priorities = within(card("Readiness priorities"));
    expect(priorities.getByRole("link", { name: "Data Intelligence" })).toHaveAttribute(
      "href",
      `/dimensions/data_intelligence?idea=${IDEA_ID}`,
    );
    expect(priorities.getByText("Invest in analytics capabilities.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Idea IQ" }));
    expect(screen.getByRole("group", { name: /Idea compass/ })).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: /Readiness compass/ })).not.toBeInTheDocument();
    const ideaPriorities = within(card("Idea priorities"));
    expect(ideaPriorities.getByText("3 / 10 · Continuous Improvement")).toBeInTheDocument();
    expect(ideaPriorities.getByText("Adopt agile ways of working.")).toBeInTheDocument();
  });

  it("asks the server for another idea's scores when one is picked", async () => {
    const two = fakeDashboard();
    two.ideas.push({
      idea_id: OTHER_IDEA,
      title: "Loyalty app",
      assessment_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
      iq: "55.0",
      confirmed_at: "2026-10-20T09:30:00Z",
    });
    const other = fakeDashboard({ ideas: two.ideas });
    other.iq = { ...other.iq!, idea_id: OTHER_IDEA, idea_title: "Loyalty app", iq: "55.0", vfm: null };
    let asked = false;
    const calls = stubApi({ ...base(two), "GET /api/v1/dashboard": () => (asked ? other : two) });
    const user = userEvent.setup();
    renderWithMe(<DashboardPage />, fakeMe());

    const select = await screen.findByRole("combobox", { name: "Idea" });
    asked = true;
    await user.selectOptions(select, "Loyalty app");
    expect(calls.filter((c) => c.path === "/api/v1/dashboard")).toHaveLength(2);

    expect(await screen.findByText("IQ of Loyalty app")).toBeInTheDocument();
    expect(screen.getByText("55.0")).toBeInTheDocument();
    expect(screen.getByText("Not calculable.")).toBeInTheDocument();
    // Readiness is untouched by the choice of idea.
    expect(within(card("Innovation Readiness")).getByText("190")).toBeInTheDocument();
  });

  it("keeps the next step on a side that has no result yet", async () => {
    stubApi({
      ...base({ ...EMPTY_DASHBOARD, readiness: fakeDashboard().readiness }),
      "GET /api/v1/ideas": [],
    });
    renderWithMe(<DashboardPage />, fakeMe());

    expect(await screen.findByRole("heading", { name: "Innovation Readiness" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Ideas" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Add an idea" })).toBeInTheDocument();
    // One compass, so nothing to switch between.
    expect(screen.queryByRole("button", { name: "Idea IQ" })).not.toBeInTheDocument();
    expect(screen.getByRole("group", { name: /Readiness compass/ })).toBeInTheDocument();
  });
});
