import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import {
  fakeInvitation,
  fakeMe,
  fakeMember,
  fakeOrganisation,
  stubApi,
} from "@/test/api";
import { renderWithMe } from "@/test/me";

import { TeamPage } from "./TeamPage";

describe("TeamPage", () => {
  it("lets an owner invite someone and shows the new invitation", async () => {
    const calls = stubApi({
      "GET /api/v1/organisation": fakeOrganisation(),
      "GET /api/v1/organisation/members": [fakeMember()],
      "GET /api/v1/organisation/invitations": [],
      "POST /api/v1/organisation/invitations": fakeInvitation({ email: "new@example.com" }),
    });
    const user = userEvent.setup();

    renderWithMe(<TeamPage />, fakeMe());
    await user.type(await screen.findByLabelText("Email"), "new@example.com");
    await user.selectOptions(screen.getByLabelText("Role"), "member");
    await user.click(screen.getByRole("button", { name: "Send invitation" }));

    expect(calls.at(-1)).toMatchObject({
      method: "POST",
      path: "/api/v1/organisation/invitations",
      body: { email: "new@example.com", role: "member" },
    });
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Invitation sent to new@example.com.",
    );
    const waiting = screen.getByRole("heading", { name: "Invitations waiting" });
    expect(waiting).toBeInTheDocument();
  });

  it("lets an owner give the owner role, and cancels an invitation", async () => {
    const member = fakeMember({
      id: "66666666-6666-6666-6666-666666666666",
      name: "Mia Member",
      email: "mia@example.com",
      role: "member",
    });
    const calls = stubApi({
      "GET /api/v1/organisation": fakeOrganisation(),
      "GET /api/v1/organisation/members": [fakeMember(), member],
      "GET /api/v1/organisation/invitations": [fakeInvitation()],
      "PATCH /api/v1/organisation/members/66666666-6666-6666-6666-666666666666": {
        ...member,
        role: "admin",
      },
      "DELETE /api/v1/organisation/invitations/44444444-4444-4444-4444-444444444444": {
        message: "The invitation is cancelled.",
      },
    });
    const user = userEvent.setup();

    renderWithMe(<TeamPage />, fakeMe());
    await user.selectOptions(await screen.findByLabelText("Role of Mia Member"), "admin");
    expect(calls.at(-1)).toMatchObject({ method: "PATCH", body: { role: "admin" } });

    await user.click(screen.getByRole("button", { name: "Cancel" }));
    await user.click(screen.getByRole("button", { name: "Cancel invitation?" }));
    expect(calls.at(-1)).toMatchObject({
      method: "DELETE",
      path: "/api/v1/organisation/invitations/44444444-4444-4444-4444-444444444444",
    });
    expect(screen.queryByText("new@example.com")).not.toBeInTheDocument();
  });

  it("removes a member after an inline confirmation", async () => {
    const member = fakeMember({
      id: "66666666-6666-6666-6666-666666666666",
      name: "Mia Member",
      email: "mia@example.com",
      role: "member",
    });
    const calls = stubApi({
      "GET /api/v1/organisation": fakeOrganisation(),
      "GET /api/v1/organisation/members": [fakeMember(), member],
      "GET /api/v1/organisation/invitations": [],
      "DELETE /api/v1/organisation/members/66666666-6666-6666-6666-666666666666": {
        message: "The member is removed.",
      },
    });
    const user = userEvent.setup();

    renderWithMe(<TeamPage />, fakeMe());
    const row = (await screen.findByText("Mia Member")).closest("li") as HTMLElement;
    await user.click(within(row).getByRole("button", { name: "Remove" }));
    await user.click(within(row).getByRole("button", { name: "Remove member?" }));

    expect(calls.at(-1)).toMatchObject({
      method: "DELETE",
      path: "/api/v1/organisation/members/66666666-6666-6666-6666-666666666666",
    });
    expect(screen.queryByText("Mia Member")).not.toBeInTheDocument();
  });

  it("names the person's role when confirming a removal", async () => {
    stubApi({
      "GET /api/v1/organisation": fakeOrganisation(),
      "GET /api/v1/organisation/members": [
        fakeMember(),
        fakeMember({ id: "o2", user_id: "u2", name: "Otto Owner", role: "owner" }),
        fakeMember({ id: "c1", user_id: "u3", name: "Cleo Committee", role: "committee" }),
      ],
      "GET /api/v1/organisation/invitations": [],
    });
    const user = userEvent.setup();

    renderWithMe(<TeamPage />, fakeMe());
    const owner = (await screen.findByText("Otto Owner")).closest("li") as HTMLElement;
    await user.click(within(owner).getByRole("button", { name: "Remove" }));
    expect(within(owner).getByRole("button", { name: "Remove owner?" })).toBeInTheDocument();

    const committee = screen.getByText("Cleo Committee").closest("li") as HTMLElement;
    await user.click(within(committee).getByRole("button", { name: "Remove" }));
    expect(
      within(committee).getByRole("button", { name: "Remove committee member?" }),
    ).toBeInTheDocument();
  });

  it("shows a member the team without any management controls", async () => {
    stubApi({
      "GET /api/v1/organisation": fakeOrganisation({ role: "member" }),
      "GET /api/v1/organisation/members": [fakeMember(), fakeMember({ id: "x", role: "member" })],
    });

    renderWithMe(<TeamPage />, fakeMe({ memberships: [] }));
    expect(await screen.findByRole("heading", { name: "Members" })).toBeInTheDocument();

    expect(screen.queryByRole("button", { name: "Send invitation" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Remove" })).not.toBeInTheDocument();
  });

  it("tells a consultant the team list is hidden", async () => {
    stubApi({
      "GET /api/v1/organisation": fakeOrganisation({ role: "consultant" }),
    });

    renderWithMe(<TeamPage />, fakeMe({ memberships: [] }));

    expect(
      await screen.findByText("You have read-only consultant access to Acme.", { exact: false }),
    ).toBeInTheDocument();
  });

  it("asks for an organisation when none is active", () => {
    stubApi({});

    renderWithMe(<TeamPage />, fakeMe({ active_organisation_id: null, memberships: [] }));

    expect(screen.getByRole("status")).toHaveTextContent("Choose an organisation");
  });
});
