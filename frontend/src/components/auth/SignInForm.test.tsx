import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { errorResponse, fakeMe, stubApi } from "@/test/api";
import { routerPush, setLocation } from "@/test/navigation";

import { SignInForm } from "./SignInForm";

vi.mock("next/navigation", async () => (await import("@/test/navigation")).navigationMock());

async function fillAndSubmit() {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Email"), "owner@example.com");
  await user.type(screen.getByLabelText("Password"), "a-long-password");
  await user.click(screen.getByRole("button", { name: "Sign in" }));
}

describe("SignInForm", () => {
  beforeEach(() => {
    setLocation("/sign-in");
    routerPush.mockClear();
  });

  it("signs in and goes to the team page", async () => {
    const calls = stubApi({ "POST /api/v1/auth/sign-in": fakeMe() });

    render(<SignInForm />);
    await fillAndSubmit();

    expect(calls[0]?.body).toEqual({ email: "owner@example.com", password: "a-long-password" });
    expect(routerPush).toHaveBeenCalledWith("/team");
  });

  it("follows a safe ?next= path and keeps the fragment", async () => {
    setLocation("/sign-in?next=%2Finvitations%2Faccept#token=tok1");
    stubApi({ "POST /api/v1/auth/sign-in": fakeMe() });

    render(<SignInForm />);
    await fillAndSubmit();

    expect(routerPush).toHaveBeenCalledWith("/invitations/accept#token=tok1");
  });

  it("sends a new user without organisations to create one", async () => {
    stubApi({
      "POST /api/v1/auth/sign-in": fakeMe({ active_organisation_id: null, memberships: [] }),
    });

    render(<SignInForm />);
    await fillAndSubmit();

    expect(routerPush).toHaveBeenCalledWith("/organisations/new");
  });

  it("shows the backend message for wrong credentials", async () => {
    stubApi({
      "POST /api/v1/auth/sign-in": errorResponse(
        "invalid_credentials",
        "The email or password is not correct.",
        401,
      ),
    });

    render(<SignInForm />);
    await fillAndSubmit();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The email or password is not correct.",
    );
    expect(routerPush).not.toHaveBeenCalled();
  });

  it("offers to resend the confirmation email when the address is not verified", async () => {
    const calls = stubApi({
      "POST /api/v1/auth/sign-in": errorResponse(
        "email_not_verified",
        "Please confirm your email first. Check your inbox.",
        403,
      ),
      "POST /api/v1/auth/verify-email/resend": { message: "Check your inbox." },
    });

    render(<SignInForm />);
    await fillAndSubmit();
    await userEvent.click(
      await screen.findByRole("button", { name: "Send the confirmation email again" }),
    );

    expect(calls.at(-1)).toMatchObject({
      path: "/api/v1/auth/verify-email/resend",
      body: { email: "owner@example.com" },
    });
    expect(await screen.findByRole("status")).toHaveTextContent("Check your inbox");
  });
});
