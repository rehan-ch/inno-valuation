import { screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  fakeAssessmentSummary,
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
  const glance = within(screen.getByRole("region", { name: "At a glance" }));
  const card = glance.getByText(label).parentElement as HTMLElement;
  return within(card).getAllByText(/.+/)[1]?.textContent ?? "";
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
    });

    renderWithMe(<DashboardPage />, fakeMe());

    expect(await screen.findByRole("heading", { name: "Welcome back, Olive" })).toBeInTheDocument();
    expect(screen.getByText("Acme · you are an owner")).toBeInTheDocument();
    expect(stat("Team members")).toBe("2");
    expect(stat("Invitations waiting")).toBe("1"); // the expired one does not count
    expect(stat("Consultant access")).toBe("1");
    expect(stat("Currency")).toBe("USD");

    const steps = screen.getByRole("heading", { name: "Getting started" }).closest("section");
    expect(steps).not.toBeNull();
    const checklist = within(steps as HTMLElement);
    // Profile is incomplete (no country or size yet), so it stays a link to fix it.
    expect(checklist.getByRole("link", { name: "Complete the organisation profile" })).toHaveAttribute(
      "href",
      "/organisation",
    );
    // Two members means the team is invited; a live grant means the consultant has access.
    expect(checklist.queryByRole("link", { name: "Invite your team" })).not.toBeInTheDocument();
    expect(checklist.getByRole("link", { name: "Run the readiness assessment" })).toHaveAttribute(
      "href",
      "/readiness",
    );
    expect(screen.getByRole("link", { name: "Start a readiness assessment" })).toBeInTheDocument();

    expect(screen.getByText("(you)")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Invite a team member" })).toHaveAttribute(
      "href",
      "/team",
    );
  });

  it("shows a plain member the team and the readiness card, without manager figures", async () => {
    stubApi({
      "GET /api/v1/organisation": fakeOrganisation({ role: "member" }),
      "GET /api/v1/organisation/members": [fakeMember()],
      "GET /api/v1/readiness/assessments": [],
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

    expect(await screen.findByText("Acme · you are a member")).toBeInTheDocument();
    expect(screen.queryByText("Invitations waiting")).not.toBeInTheDocument();
    expect(screen.queryByText("Getting started")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Readiness assessment" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Invite a team member" })).not.toBeInTheDocument();
  });

  it("gives a consultant a read-only welcome with the access end date", async () => {
    stubApi({
      "GET /api/v1/organisation": fakeOrganisation({ role: "consultant" }),
      "GET /api/v1/readiness/assessments": [],
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
      "GET /api/v1/readiness/assessments": [
        fakeAssessmentSummary({ status: "final", total: 190, band_name: "Building Blocks" }),
      ],
    });

    renderWithMe(<DashboardPage />, fakeMe());

    expect(await screen.findByText("Building Blocks")).toBeInTheDocument();
    expect(screen.getByText("190")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "See the result" })).toHaveAttribute(
      "href",
      "/readiness/77777777-7777-7777-7777-777777777777/result",
    );
  });

  it("asks someone without an organisation to create one", () => {
    const calls = stubApi({});

    renderWithMe(<DashboardPage />, fakeMe({ active_organisation_id: null, memberships: [] }));

    expect(screen.getByRole("heading", { name: "Welcome, Olive" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Create an organisation" })).toHaveAttribute(
      "href",
      "/organisations/new",
    );
    expect(calls).toHaveLength(0);
  });
});
