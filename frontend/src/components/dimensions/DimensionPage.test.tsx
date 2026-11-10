import { screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { IDEA_ID, errorResponse, fakeDimensionDetail, fakeMe, stubApi } from "@/test/api";
import { renderWithMe } from "@/test/me";
import { routerReplace, setLocation } from "@/test/navigation";

import { DimensionPage } from "./DimensionPage";

vi.mock("next/navigation", async () => (await import("@/test/navigation")).navigationMock());

const PATH = "/api/v1/dashboard/dimensions/organizational_agility";

function card(title: string): HTMLElement {
  return screen.getByRole("heading", { name: title }).closest("section") as HTMLElement;
}

describe("DimensionPage", () => {
  it("shows the book's text and the two scores apart, each with target, gap and trend", async () => {
    setLocation(`/dimensions/organizational_agility?idea=${IDEA_ID}`);
    const calls = stubApi({ [`GET ${PATH}`]: fakeDimensionDetail() });
    renderWithMe(<DimensionPage dimensionKey="organizational_agility" />, fakeMe());

    expect(await screen.findByRole("heading", { name: "7. Organizational Agility" })).toBeInTheDocument();
    expect(calls[0]?.path).toBe(PATH);
    expect(screen.getByText("Process Innovation")).toBeInTheDocument();
    expect(screen.getByText("How quickly the organisation adapts.")).toBeInTheDocument();
    expect(screen.getByText("Decision speed")).toBeInTheDocument();

    // The fixed next-step text, exactly as sent.
    expect(within(card("Next steps from the method")).getByText("Adopt agile ways of working.")).toBeInTheDocument();
    // Room for the advice that comes later, clearly marked as not there yet.
    expect(within(card("AI advice")).getByText("Not available yet")).toBeInTheDocument();

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
    const calls = stubApi({ [`GET ${PATH}`]: fakeDimensionDetail() });
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
