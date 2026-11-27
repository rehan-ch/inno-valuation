import { act, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import {
  errorResponse,
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
    await user.click(
      await screen.findByRole("button", {
        name: "Role of Mia Member: Member",
      }),
    );

    const roleMenu = screen.getByRole("listbox", {
      name: "Role of Mia Member",
    });

    await user.click(
      within(roleMenu).getByRole("option", {
        name: "Admin",
      }),
    );

    expect(
      await screen.findByRole("button", {
        name: "Role of Mia Member: Admin",
      }),
    ).toBeInTheDocument();

    expect(calls.at(-1)).toMatchObject({
      method: "PATCH",
      body: { role: "admin" },
    });

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

  it("holds the other rows' actions while a removal is running", async () => {
    const mia = fakeMember({
      id: "66666666-6666-6666-6666-666666666666",
      name: "Mia Member",
      email: "mia@example.com",
      role: "member",
    });
    const noah = fakeMember({
      id: "77777777-7777-7777-7777-777777777777",
      name: "Noah Member",
      email: "noah@example.com",
      role: "member",
    });
    let releaseRemove: () => void = () => { };
    stubApi({
      "GET /api/v1/organisation": fakeOrganisation(),
      "GET /api/v1/organisation/members": [fakeMember(), mia, noah],
      "GET /api/v1/organisation/invitations": [],
      "DELETE /api/v1/organisation/members/66666666-6666-6666-6666-666666666666": () =>
        new Promise((resolve) => {
          releaseRemove = () => resolve({ message: "The member is removed." });
        }),
    });
    const user = userEvent.setup();

    renderWithMe(<TeamPage />, fakeMe());
    const miaRow = (await screen.findByText("Mia Member")).closest("li") as HTMLElement;
    const noahRow = screen.getByText("Noah Member").closest("li") as HTMLElement;
    await user.click(within(miaRow).getByRole("button", { name: "Remove" }));
    await user.click(within(miaRow).getByRole("button", { name: "Remove member?" }));

    expect(within(noahRow).getByRole("button", { name: "Remove" })).toBeDisabled();
    expect(
      screen.getByRole("button", {
        name: /^Role of Noah Member:/,
      })
    ).toBeDisabled();
    await act(async () => {
      releaseRemove();
    });

    await vi.waitFor(() => expect(screen.queryByText("Mia Member")).not.toBeInTheDocument());
    expect(within(noahRow).getByRole("button", { name: "Remove" })).toBeEnabled();
    expect(
      screen.getByRole("button", {
        name: /^Role of Noah Member:/,
      })
    ).toBeEnabled();
  });

  it("closes the removal question again when the removal fails", async () => {
    const mia = fakeMember({
      id: "66666666-6666-6666-6666-666666666666",
      name: "Mia Member",
      email: "mia@example.com",
      role: "member",
    });
    stubApi({
      "GET /api/v1/organisation": fakeOrganisation(),
      "GET /api/v1/organisation/members": [fakeMember(), mia],
      "GET /api/v1/organisation/invitations": [],
      "DELETE /api/v1/organisation/members/66666666-6666-6666-6666-666666666666": errorResponse(
        "last_owner",
        "The organisation needs at least one owner.",
        409,
      ),
    });
    const user = userEvent.setup();

    renderWithMe(<TeamPage />, fakeMe());
    const row = (await screen.findByText("Mia Member")).closest("li") as HTMLElement;
    await user.click(within(row).getByRole("button", { name: "Remove" }));
    await user.click(within(row).getByRole("button", { name: "Remove member?" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The organisation needs at least one owner.",
    );
    expect(within(row).getByRole("button", { name: "Remove" })).toBeEnabled();
    expect(within(row).queryByRole("button", { name: "Remove member?" })).not.toBeInTheDocument();
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
    // A member is not sent the invitations, so no count of them is shown.
    expect(screen.queryByText("Pending invitations")).not.toBeInTheDocument();
  });

  it("tells a consultant the team list is hidden", async () => {
    stubApi({
      "GET /api/v1/organisation": fakeOrganisation({ role: "consultant" }),
    });

    renderWithMe(<TeamPage />, fakeMe({ memberships: [] }));

    expect(
      await screen.findByText("You have read-only consultant access to Acme.", { exact: false }),
    ).toBeInTheDocument();
    // A consultant is not sent the team list, so no member count is shown.
    expect(screen.queryByText(/team members$/)).not.toBeInTheDocument();
  });

  it("drops the old team at once after a switch in the header", async () => {
    const BETA = "99999999-9999-9999-9999-999999999999";
    let current: "acme" | "beta" = "acme";
    let releaseLoad: () => void = () => {};
    stubApi({
      "GET /api/v1/organisation": () =>
        current === "acme"
          ? fakeOrganisation()
          : new Promise((resolve) => {
              releaseLoad = () => resolve(fakeOrganisation({ id: BETA, name: "Beta Ltd" }));
            }),
      "GET /api/v1/organisation/members": () =>
        current === "acme"
          ? [fakeMember()]
          : [fakeMember({ id: "55555555-5555-5555-5555-555555555555", name: "Bea Beta" })],
      "GET /api/v1/organisation/invitations": [],
    });
    const me = fakeMe();

    const { setMe } = renderWithMe(<TeamPage />, me);
    expect(await screen.findByText("Olive Owner")).toBeInTheDocument();

    current = "beta";
    setMe({ ...me, active_organisation_id: BETA });

    // While the new organisation loads, nothing of the old one is left to act on.
    expect(await screen.findByText("Loading the team...")).toBeInTheDocument();
    expect(screen.queryByText("Olive Owner")).not.toBeInTheDocument();
    releaseLoad();
    expect(await screen.findByText("Bea Beta")).toBeInTheDocument();
  });

  it("asks for an organisation when none is active", () => {
    stubApi({});

    renderWithMe(<TeamPage />, fakeMe({ active_organisation_id: null, memberships: [] }));

    expect(screen.getByRole("status")).toHaveTextContent("Choose an organisation");
  });
});
