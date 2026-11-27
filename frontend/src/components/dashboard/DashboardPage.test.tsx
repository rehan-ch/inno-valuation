import { screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  EMPTY_DASHBOARD,
  fakeAssessmentSummary,
  fakeDashboard,
  fakeGrant,
  fakeInvitation,
  fakeMe,
  fakeMember,
  fakeOrganisation,
  stubApi,
} from "@/test/api";
import { renderWithMe } from "@/test/me";

import { DashboardPage } from "./DashboardPage";

vi.mock("next/navigation", async () => (await import("@/test/navigation")).navigationMock());

function stat(label: string): string {
  const glance = within(
    screen.getByRole("region", { name: "At a glance" })
  );

  const labelElement = glance.getByText(label);
  const card = labelElement.closest(".iv-metric-card");

  if (!card) {
    throw new Error(`Metric card not found: ${label}`);
  }

  return (
    card.querySelector(".iv-metric-value")?.textContent?.trim() ?? ""
  );
}

describe("DashboardPage", () => {
  it("welcomes an owner with the organisation at a glance and the next steps", async () => {
    stubApi({
      "GET /api/v1/organisation": fakeOrganisation({ industry: "Retail" }),
      "GET /api/v1/organisation/members": [
        fakeMember(),
        fakeMember({ id: "m2", user_id: "u2", name: "Mia Member", role: "member" }),
      ],
      "GET /api/v1/organisation/invitations": [
        fakeInvitation(),
        fakeInvitation({ id: "i2", email: "old@example.com", expired: true }),
      ],
      "GET /api/v1/organisation/consultants": [fakeGrant({ status: "active" })],
      "GET /api/v1/readiness/assessments": [],
      "GET /api/v1/ideas": [],
      "GET /api/v1/dashboard": EMPTY_DASHBOARD,
    });

    renderWithMe(<DashboardPage />, fakeMe());

    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: /^Welcome back,\s*Olive\s*\.$/,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Acme")).toBeInTheDocument();

    expect(
      screen.getByText("an owner"),
    ).toBeInTheDocument();
    expect(stat("Team members")).toBe("2");
    expect(stat("Pending invitations")).toBe("1"); // the expired one does not count
    expect(stat("Consultant access")).toBe("1");
    expect(stat("Currency")).toBe("USD");

    const steps = screen.getByRole("heading", { name: "Getting started" }).closest("section");
    expect(steps).not.toBeNull();
    const checklist = within(steps as HTMLElement);
    // Profile is incomplete (no country or size yet), so it stays a link to fix it.

    // The organisation profile is incomplete.
    const profileLinks = checklist.getAllByRole("link", {
      name: "Complete organisation profile",
    });

    expect(profileLinks[0]).toHaveAttribute(
      "href",
      "/organisation",
    );

    // Two members means the team is already invited.
    expect(
      checklist.queryByRole("link", {
        name: "Invite your team",
      }),
    ).not.toBeInTheDocument();

    // A readiness assessment has not been completed yet.
    const readinessLinks = checklist.getAllByRole("link", {
      name: "Run the readiness assessment",
    });

    expect(readinessLinks[0]).toHaveAttribute(
      "href",
      "/readiness",
    );

    // The main readiness action is available.
    expect(
      screen.getByRole("link", {
        name: "Start assessment",
      }),
    ).toHaveAttribute("href", "/readiness");

    // The signed-in user appears in the team card.
    expect(screen.getByText("(you)")).toBeInTheDocument();

    // A manager is offered the invite shortcut, and it goes to the team page.
    expect(
      screen.getByRole("link", { name: /^Invite a member/ }),
    ).toHaveAttribute("href", "/team");
  });

  it("leaves ideas out, and does not ask for them, while the AI is switched off", async () => {
    // No "GET /api/v1/ideas" here: the stub fails the test if the page asks for it.
    stubApi({
      "GET /api/v1/organisation": fakeOrganisation(),
      "GET /api/v1/organisation/members": [fakeMember()],
      "GET /api/v1/organisation/invitations": [],
      "GET /api/v1/organisation/consultants": [],
      "GET /api/v1/readiness/assessments": [],
      "GET /api/v1/dashboard": EMPTY_DASHBOARD,
    });

    renderWithMe(<DashboardPage />, fakeMe({ ai_enabled: false }));

    expect(await screen.findByRole("heading", { name: "Getting started" })).toBeInTheDocument();
    expect(screen.getByText("Run the readiness assessment")).toBeInTheDocument();
    expect(screen.queryByText("Score your first idea")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Add an idea" })).not.toBeInTheDocument();
  });

  it("shows a plain member the team and the readiness card, without manager figures", async () => {
    stubApi({
      "GET /api/v1/organisation": fakeOrganisation({ role: "member" }),
      "GET /api/v1/organisation/members": [fakeMember()],
      "GET /api/v1/readiness/assessments": [],
      "GET /api/v1/ideas": [],
      "GET /api/v1/dashboard": EMPTY_DASHBOARD,
    });

    renderWithMe(
      <DashboardPage />,
      fakeMe({
        memberships: [
          {
            organisation_id: "22222222-2222-2222-2222-222222222222",
            organisation_name: "Acme",
            organisation_status: "active",
            role: "member",
          },
        ],
      }),
    );

    expect(
      (await screen.findAllByText("Acme")).length
    ).toBeGreaterThan(0);

    expect(
      screen.getByText("a member"),
    ).toBeInTheDocument();
    expect(screen.queryByText("Pending invitations")).not.toBeInTheDocument();
    expect(screen.queryByText("Consultant access")).not.toBeInTheDocument();
    expect(screen.queryByText("Getting started")).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        name: "Know where you stand.",
      })
    ).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^Invite a member/ })).not.toBeInTheDocument();
  });

  it("gives a consultant a read-only welcome with the access end date", async () => {
    stubApi({
      "GET /api/v1/organisation": fakeOrganisation({ role: "consultant" }),
      "GET /api/v1/readiness/assessments": [],
      "GET /api/v1/ideas": [],
      "GET /api/v1/dashboard": EMPTY_DASHBOARD,
    });

    renderWithMe(
      <DashboardPage />,
      fakeMe({
        memberships: [],
        consultant_organisations: [
          {
            organisation_id: "22222222-2222-2222-2222-222222222222",
            organisation_name: "Acme",
            organisation_status: "active",
            access_ends_at: "2026-12-31T23:59:59Z",
          },
        ],
      }),
    );

    expect(
      await screen.findByText("You have read-only consultant access to Acme until Dec 31, 2026."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "My access" })).toBeInTheDocument();
  });

  it("shows the latest final readiness result", async () => {
    stubApi({
      "GET /api/v1/organisation": fakeOrganisation({ role: "member" }),
      "GET /api/v1/organisation/members": [fakeMember()],
      "GET /api/v1/ideas": [],
      "GET /api/v1/dashboard": EMPTY_DASHBOARD,
      "GET /api/v1/readiness/assessments": [
        fakeAssessmentSummary({ status: "final", total: 190, band_name: "Building Blocks" }),
      ],
    });

    renderWithMe(<DashboardPage />, fakeMe());

    expect(await screen.findByText("Building Blocks")).toBeInTheDocument();
    expect(screen.getByText("190")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View results" })).toHaveAttribute(
      "href",
      "/readiness/77777777-7777-7777-7777-777777777777/result",
    );
  });

  it("keeps the newer assessment and the ideas entry point once there are scores", async () => {
    stubApi({
      "GET /api/v1/organisation": fakeOrganisation(),
      "GET /api/v1/organisation/members": [fakeMember()],
      "GET /api/v1/organisation/invitations": [],
      "GET /api/v1/organisation/consultants": [],
      "GET /api/v1/readiness/assessments": [
        fakeAssessmentSummary({ status: "collecting", my_status: "not_started" }),
      ],
      "GET /api/v1/ideas": [],
      "GET /api/v1/dashboard": fakeDashboard(),
    });

    renderWithMe(<DashboardPage />, fakeMe());

    // The scores are shown, and a second assessment under way still asks for answers.
    expect(
      await screen.findByRole("link", { name: "Continue assessment" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Add an idea" })).toHaveAttribute(
      "href",
      "/ideas/new",
    );
  });

  it("asks someone without an organisation to create one", () => {
    const calls = stubApi({});

    renderWithMe(<DashboardPage />, fakeMe({ active_organisation_id: null, memberships: [] }));

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /^Welcome back,\s*Olive\s*\.$/,
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Create an organisation" })).toHaveAttribute(
      "href",
      "/organisations/new",
    );
    expect(calls).toHaveLength(0);
  });
});
