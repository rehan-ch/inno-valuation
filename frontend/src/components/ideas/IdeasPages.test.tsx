import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import {
  IDEA_ID,
  IQ_ASSESSMENT_ID,
  fakeConfirmedAssessment,
  fakeIdea,
  fakeIdeaSummary,
  fakeIqAssessment,
  fakeMe,
  fakeOrganisation,
  stubApi,
} from "@/test/api";
import type { RecordedCall } from "@/test/api";
import { renderWithMe } from "@/test/me";
import { routerPush } from "@/test/navigation";

import { AssessmentPage } from "./AssessmentPage";
import { IdeaForm } from "./IdeaForm";
import { IdeasListPage, sortIdeas } from "./IdeasListPage";

vi.mock("next/navigation", async () => (await import("@/test/navigation")).navigationMock());

const A = `/api/v1/ideas/${IDEA_ID}/assessments/${IQ_ASSESSMENT_ID}`;

function scored(id: string, title: string, iq: string, vfm: string | null, currency = "USD") {
  return fakeIdeaSummary({
    id,
    title,
    status: "assessed",
    currency,
    latest_assessment: {
      id: `a-${id}`,
      status: "confirmed",
      proposal_status: "ready",
      sample: false,
      iq,
      vfm_per_point: vfm,
      currency,
      requested_at: "2026-10-28T09:05:00Z",
      confirmed_at: "2026-10-28T10:00:00Z",
    },
  });
}

describe("IdeasListPage", () => {
  it("shows each idea's IQ and Value for Money and sorts by IQ", async () => {
    stubApi({
      "GET /api/v1/ideas": [
        fakeIdeaSummary({ id: "d1", title: "Draft one" }),
        scored("s1", "Low idea", "45.0", "1111.11"),
        scored("s2", "High idea", "70.0", "714.29"),
      ],
    });
    const user = userEvent.setup();

    renderWithMe(<IdeasListPage />, fakeMe());

    const rows = within(await screen.findByRole("table")).getAllByRole("row").slice(1);
    expect(rows.map((r) => within(r).getAllByRole("cell")[1]?.textContent)).toEqual([
      expect.stringContaining("Draft one"),
      expect.stringContaining("Low idea"),
      expect.stringContaining("High idea"),
    ]);
    expect(screen.getByText("714.29", { exact: false })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Add an idea" })).toHaveAttribute("href", "/ideas/new");

    await user.selectOptions(screen.getByRole("combobox", { name: "Sort ideas" }), "iq");
    const sorted = within(screen.getByRole("table")).getAllByRole("row").slice(1);
    expect(sorted[0]).toHaveTextContent("High idea");
    expect(sorted[2]).toHaveTextContent("Draft one"); // unscored ideas go last

    await user.click(screen.getByRole("checkbox", { name: "Compare High idea" }));
    await user.click(screen.getByRole("checkbox", { name: "Compare Low idea" }));
    expect(screen.getByRole("link", { name: "Compare 2 ideas" })).toHaveAttribute(
      "href",
      "/ideas/compare?ids=s2,s1",
    );
  });

  it("hides the add button from an investor", async () => {
    stubApi({ "GET /api/v1/ideas": [] });
    const me = fakeMe();
    me.memberships = me.memberships.map((m) => ({ ...m, role: "investor" as const }));
    renderWithMe(<IdeasListPage />, me);
    expect(await screen.findByText("No ideas yet.")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Add an idea" })).not.toBeInTheDocument();
  });
});

describe("sortIdeas", () => {
  it("puts the lowest cost per point first and ideas without one last", () => {
    const ideas = [
      scored("a", "A", "60.0", "900.00"),
      scored("b", "B", "70.0", null),
      scored("c", "C", "50.0", "500.00"),
    ];
    expect(sortIdeas(ideas, "vfm").map((i) => i.title)).toEqual(["C", "A", "B"]);
    expect(sortIdeas(ideas, "iq").map((i) => i.title)).toEqual(["B", "A", "C"]);
    expect(sortIdeas(ideas, "newest").map((i) => i.title)).toEqual(["A", "B", "C"]);
  });
});

describe("IdeaForm", () => {
  it("saves a new idea in the organisation's currency and opens it", async () => {
    routerPush.mockClear();
    const calls = stubApi({
      "GET /api/v1/organisation": fakeOrganisation({ currency: "EUR" }),
      "POST /api/v1/ideas": (call: RecordedCall) =>
        fakeIdea({ ...(call.body as object), id: IDEA_ID }),
    });
    const user = userEvent.setup();

    renderWithMe(<IdeaForm />, fakeMe());
    await user.type(await screen.findByLabelText("Title"), "Same-day delivery");
    await user.type(screen.getByLabelText("Summary"), "Local shops deliver within two hours.");
    await user.type(screen.getByLabelText("Planned investment"), "50000.5");
    await user.click(screen.getByRole("button", { name: "Save idea" }));

    const post = calls.find((c) => c.method === "POST");
    expect(post?.body).toMatchObject({
      title: "Same-day delivery",
      summary: "Local shops deliver within two hours.",
      currency: "EUR",
      investment: "50000.5",
      stage: "idea",
    });
    expect(routerPush).toHaveBeenCalledWith(`/ideas/${IDEA_ID}`);
  });

  it("refuses more decimals than the currency has before sending", async () => {
    const calls = stubApi({ "GET /api/v1/organisation": fakeOrganisation({ currency: "JPY" }) });
    const user = userEvent.setup();

    renderWithMe(<IdeaForm />, fakeMe());
    await user.type(await screen.findByLabelText("Title"), "Yen idea");
    await user.type(screen.getByLabelText("Summary"), "Priced in yen.");
    await user.type(screen.getByLabelText("Planned investment"), "100.50");
    await user.click(screen.getByRole("button", { name: "Save idea" }));

    expect(screen.getByText("JPY amounts have no decimals.")).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "POST")).toHaveLength(0);
  });
});

describe("AssessmentPage", () => {
  it("lets the owner change a proposed score, saves it, and confirms", async () => {
    const calls = stubApi({
      [`GET ${A}`]: fakeIqAssessment(),
      [`PATCH ${A}/review`]: (call: RecordedCall) => {
        const scores = (call.body as { scores: Record<string, number | null> }).scores;
        const base = fakeIqAssessment();
        return {
          ...base,
          dimensions: base.dimensions.map((d) =>
            d.key in scores
              ? { ...d, final_score: scores[d.key], changed: scores[d.key] !== null }
              : d,
          ),
        };
      },
      [`POST ${A}/confirm`]: fakeConfirmedAssessment(),
    });
    const user = userEvent.setup();

    renderWithMe(<AssessmentPage ideaId={IDEA_ID} assessmentId={IQ_ASSESSMENT_ID} />, fakeMe());
    expect(await screen.findByText("No scores changed")).toBeInTheDocument();
    expect(screen.getAllByText("Proposed by AI: 4")).toHaveLength(3);

    await user.click(screen.getByRole("radio", { name: "Organizational Agility: 5" }));
    expect(await screen.findByText("1 of 3 scores changed")).toBeInTheDocument();
    expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({
      scores: { organizational_agility: 5 },
      notes: {},
    });
    expect(await screen.findByText("Saved")).toBeInTheDocument();

    // Choosing the proposed score again puts the proposal back.
    await user.click(screen.getByRole("radio", { name: "Organizational Agility: 4" }));
    expect(calls.filter((c) => c.method === "PATCH").at(-1)?.body).toEqual({
      scores: { organizational_agility: null },
      notes: {},
    });

    await user.click(screen.getByRole("button", { name: "Confirm the scores" }));
    await user.click(screen.getByRole("button", { name: "Confirm now" }));
    expect(await screen.findByText("70.0")).toBeInTheDocument();
    expect(calls.at(-1)).toMatchObject({ method: "POST", path: `${A}/confirm` });
  });

  it("shows a confirmed result with the IQ, Value for Money and the changed score", async () => {
    stubApi({ [`GET ${A}`]: fakeConfirmedAssessment() });

    renderWithMe(<AssessmentPage ideaId={IDEA_ID} assessmentId={IQ_ASSESSMENT_ID} />, fakeMe());

    expect(await screen.findByText("70.0")).toBeInTheDocument();
    expect(screen.getByText("$714.29")).toBeInTheDocument();
    expect(screen.getByText("changed from 4")).toBeInTheDocument();
    expect(screen.getByText("The team has reorganised twice this year.")).toBeInTheDocument();
    expect(screen.getByText("Build adaptable structures.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Confirm the scores" })).not.toBeInTheDocument();
  });

  it("does not let the owner confirm while a change failed to save", async () => {
    stubApi({
      [`GET ${A}`]: fakeIqAssessment(),
      [`PATCH ${A}/review`]: () =>
        new Response(
          JSON.stringify({ error: { code: "server_error", message: "Something went wrong." } }),
          { status: 500, headers: { "Content-Type": "application/json" } },
        ),
    });
    const user = userEvent.setup();
    renderWithMe(<AssessmentPage ideaId={IDEA_ID} assessmentId={IQ_ASSESSMENT_ID} />, fakeMe());
    expect(await screen.findByText("No scores changed")).toBeInTheDocument();

    await user.click(screen.getByRole("radio", { name: "Organizational Agility: 5" }));
    const status = await screen.findByRole("status", { name: "Save status" });
    expect(status).not.toHaveTextContent("Saved");
    expect(status.textContent).not.toBe("");
    // The IQ would be worked out from the server's older score, so confirming waits.
    expect(screen.getByRole("button", { name: "Confirm the scores" })).toBeDisabled();
  });

  it("explains a failed proposal and offers to try again", async () => {
    stubApi({ [`GET ${A}`]: fakeIqAssessment({ proposal_status: "failed" }) });
    renderWithMe(<AssessmentPage ideaId={IDEA_ID} assessmentId={IQ_ASSESSMENT_ID} />, fakeMe());
    expect(
      await screen.findByText("The proposal could not be made this time. Nothing was scored."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
});
