import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { InvitationPreviewOut } from "@/lib/api/types";
import { errorResponse, fakeMe, stubApi } from "@/test/api";
import { routerPush, setLocation } from "@/test/navigation";

import { AcceptInvitation } from "./AcceptInvitation";

vi.mock("next/navigation", async () => (await import("@/test/navigation")).navigationMock());

const PREVIEW: InvitationPreviewOut = {
  organisation_name: "Acme",
  email: "owner@example.com",
  role: "member",
  expires_at: "2026-10-21T10:00:00Z",
};

describe("AcceptInvitation", () => {
  beforeEach(() => routerPush.mockClear());

  it("shows the invitation and joins when the signed-in email matches", async () => {
    setLocation("/invitations/accept#token=inv1");
    const calls = stubApi({
      "POST /api/v1/invitations/preview": PREVIEW,
      "GET /api/v1/me": fakeMe(),
      "POST /api/v1/invitations/accept": fakeMe(),
    });
    const user = userEvent.setup();

    render(<AcceptInvitation />);
    expect(await screen.findByRole("heading", { name: "Join Acme" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Accept invitation" }));

    expect(calls.at(-1)).toMatchObject({
      path: "/api/v1/invitations/accept",
      body: { token: "inv1" },
    });
    expect(routerPush).toHaveBeenCalledWith("/dashboard");
  });

  it("asks a signed-out visitor to sign in, keeping the token in the fragment", async () => {
    setLocation("/invitations/accept#token=inv1");
    stubApi({
      "POST /api/v1/invitations/preview": PREVIEW,
      "GET /api/v1/me": errorResponse("not_authenticated", "Please sign in.", 401),
    });

    render(<AcceptInvitation />);

    const signIn = await screen.findByRole("link", { name: "Sign in" });
    expect(signIn).toHaveAttribute("href", "/sign-in?next=%2Finvitations%2Faccept#token=inv1");
  });

  it("warns when signed in with a different email", async () => {
    setLocation("/invitations/accept#token=inv1");
    stubApi({
      "POST /api/v1/invitations/preview": PREVIEW,
      "GET /api/v1/me": fakeMe({ email: "other@example.com" }),
    });

    render(<AcceptInvitation />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This invitation is for owner@example.com, but you are signed in as other@example.com.",
    );
  });

  it("explains when the link is missing or stale", async () => {
    setLocation("/invitations/accept");
    stubApi({});

    render(<AcceptInvitation />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This page needs the link from an invitation email.",
    );
  });
});
