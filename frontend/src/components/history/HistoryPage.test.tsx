import { screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { IDEA_ID, IQ_ASSESSMENT_ID, fakeDashboard, fakeMe, stubApi } from "@/test/api";
import { renderWithMe } from "@/test/me";
import { setLocation } from "@/test/navigation";
import type { IdeaHistoryOut, ReadinessHistoryOut } from "@/lib/api/types";

import { HistoryPage } from "./HistoryPage";

vi.mock("next/navigation", async () => (await import("@/test/navigation")).navigationMock());

const NEW = "55555555-5555-5555-5555-555555555555";
const OLD = "66666666-6666-6666-6666-666666666666";

const dimension = (score: number, change: number | null, extra = {}) => ({
  key: "customer_journey",
  name: "Customer Journey",
  order: 1,
  score,
  maximum: 25,
  change,
  direction: change === null ? null : change > 0 ? ("up" as const) : change < 0 ? ("down" as const) : ("same" as const),
  target: null,
  gap: null,
  ...extra,
});

const READINESS: ReadinessHistoryOut = {
  entries: [
    {
      assessment_id: NEW,
      finalised_at: "2026-10-20T10:00:00Z",
      question_set_version: 1,
      total: 190,
      total_maximum: 300,
      band_name: "Building Blocks",
      compared_with: OLD,
      total_change: 25,
      total_direction: "up",
      dimensions: [dimension(20, 5, { target: 22, gap: 2 })],
    },
    {
      assessment_id: OLD,
      finalised_at: "2026-09-01T10:00:00Z",
      question_set_version: 1,
      total: 165,
      total_maximum: 300,
      band_name: "Emerging Innovator",
      compared_with: null,
      total_change: null,
      total_direction: null,
      dimensions: [dimension(15, null, { target: 22, gap: 7 })],
    },
  ],
};

const IDEA: IdeaHistoryOut = {
  idea_id: IDEA_ID,
  idea_title: "Same-day delivery",
  entries: [
    {
      assessment_id: IQ_ASSESSMENT_ID,
      confirmed_at: "2026-10-28T09:30:00Z",
      question_set_version: 1,
      iq: "70.0",
      iq_maximum: "100.0",
      compared_with: "old-iq",
      iq_change: "0.8",
      iq_direction: "up",
      vfm: { investment: "50000.00", currency: "USD", per_point: "714.29", not_calculable_reason: null },
      vfm_change: "-8.25",
      vfm_direction: "down",
      dimensions: [{ ...dimension(8, 1), maximum: 10 }],
    },
    {
      assessment_id: "old-iq",
      confirmed_at: "2026-09-28T09:30:00Z",
      question_set_version: 1,
      iq: "69.2",
      iq_maximum: "100.0",
      compared_with: null,
      iq_change: null,
      iq_direction: null,
      vfm: { investment: "50000.00", currency: "USD", per_point: "722.54", not_calculable_reason: null },
      vfm_change: null,
      vfm_direction: null,
      dimensions: [{ ...dimension(7, null), maximum: 10 }],
    },
  ],
};

describe("HistoryPage", () => {
  it("shows readiness and one idea over time as two separate tables with the server's changes", async () => {
    setLocation("/history");
    const calls = stubApi({
      "GET /api/v1/history/readiness": READINESS,
      "GET /api/v1/dashboard": fakeDashboard(),
      [`GET /api/v1/history/ideas/${IDEA_ID}`]: IDEA,
    });
    renderWithMe(<HistoryPage />, fakeMe());

    const readiness = within(await screen.findByRole("table", { name: "Readiness results over time" }));
    // An earlier result opens as it was.
    expect(readiness.getByRole("link", { name: "Sep 1, 2026" })).toHaveAttribute(
      "href",
      `/readiness/${OLD}/result`,
    );
    const total = readiness.getByRole("row", { name: /Readiness score/ });
    expect(total).toHaveTextContent("190 / 300");
    expect(total).toHaveTextContent("+25");
    expect(total).toHaveTextContent("165 / 300");
    expect(readiness.getByRole("row", { name: /Band/ })).toHaveTextContent("Building BlocksEmerging Innovator");
    const journey = readiness.getByRole("row", { name: /Customer Journey/ });
    expect(journey).toHaveTextContent("20 / 25");
    expect(journey).toHaveTextContent("+5");
    expect(journey).toHaveTextContent("2 below target");

    const idea = within(screen.getByRole("table", { name: "Scorings of the idea over time" }));
    const iq = idea.getByRole("row", { name: /^IQ/ });
    expect(iq).toHaveTextContent("70.0 / 100");
    expect(iq).toHaveTextContent("+0.8");
    const vfm = idea.getByRole("row", { name: /Value for money/ });
    expect(vfm).toHaveTextContent("$714.29");
    expect(vfm).toHaveTextContent("−8.25"); // the number went down; lower is better
    expect(vfm).toHaveTextContent("$722.54");
    // The two scales never share a table.
    expect(readiness.queryByText(/70\.0/)).not.toBeInTheDocument();
    expect(idea.queryByText(/190/)).not.toBeInTheDocument();

    expect(calls.map((c) => c.path)).toContain(`/api/v1/history/ideas/${IDEA_ID}`);
    expect(screen.getAllByRole("button", { name: "Export as CSV" })).toHaveLength(2);
  });

  it("says so when there is nothing to compare yet", async () => {
    setLocation("/history");
    stubApi({
      "GET /api/v1/history/readiness": { entries: [] },
      "GET /api/v1/dashboard": { readiness: null, ideas: [], iq: null },
    });
    renderWithMe(<HistoryPage />, fakeMe());

    expect(await screen.findByText("No final readiness result yet")).toBeInTheDocument();
    expect(screen.getByText("No idea has confirmed scores yet")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Export as CSV" })).not.toBeInTheDocument();
  });
});
