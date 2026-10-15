import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { stubApi } from "@/test/api";
import { setLocation } from "@/test/navigation";

import { ForgotPasswordForm } from "./ForgotPasswordForm";
import { ResetPasswordForm } from "./ResetPasswordForm";

describe("ForgotPasswordForm", () => {
  it("requests a reset link and shows the check-inbox message", async () => {
    const calls = stubApi({
      "POST /api/v1/auth/password/forgot": { message: "Check your inbox." },
    });
    const user = userEvent.setup();

    render(<ForgotPasswordForm />);
    await user.type(screen.getByLabelText("Email"), "me@example.com");
    await user.click(screen.getByRole("button", { name: "Send reset link" }));

    expect(calls[0]?.body).toEqual({ email: "me@example.com" });
    expect(await screen.findByRole("status")).toHaveTextContent("Check your inbox.");
  });
});

describe("ResetPasswordForm", () => {
  it("changes the password with the token from the fragment", async () => {
    setLocation("/reset-password#token=tok9");
    const calls = stubApi({
      "POST /api/v1/auth/password/reset": { message: "Your password is changed." },
    });
    const user = userEvent.setup();

    render(<ResetPasswordForm />);
    await user.type(await screen.findByLabelText("New password"), "a-new-password");
    await user.click(screen.getByRole("button", { name: "Change password" }));

    expect(calls[0]?.body).toEqual({ token: "tok9", new_password: "a-new-password" });
    expect(await screen.findByRole("status")).toHaveTextContent("Your password is changed.");
  });

  it("points to the forgot-password page when there is no token", async () => {
    setLocation("/reset-password");
    stubApi({});

    render(<ResetPasswordForm />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This page needs the link from the password reset email.",
    );
  });
});
