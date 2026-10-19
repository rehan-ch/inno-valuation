import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { errorResponse, stubApi } from "@/test/api";
import { setLocation } from "@/test/navigation";

import { VerifyEmail } from "./VerifyEmail";

describe("VerifyEmail", () => {
  it("verifies the token from the fragment and clears it from the URL", async () => {
    setLocation("/verify-email#token=tok1");
    const calls = stubApi({
      "POST /api/v1/auth/verify-email": { message: "Your email is confirmed." },
    });

    render(<VerifyEmail />);

    expect(await screen.findByText("Your email is confirmed.")).toBeInTheDocument();
    expect(calls[0]?.body).toEqual({ token: "tok1" });
    expect(window.location.hash).toBe("");
  });

  it("asks for a password when the link requires one, then verifies", async () => {
    setLocation("/verify-email#token=tok2");
    let attempts = 0;
    const calls = stubApi({
      "POST /api/v1/auth/verify-email": () => {
        attempts += 1;
        return attempts === 1
          ? errorResponse("password_required", "Choose a password.", 400)
          : { message: "Your email is confirmed." };
      },
    });
    const user = userEvent.setup();

    render(<VerifyEmail />);
    await user.type(await screen.findByLabelText("New password"), "a-long-password");
    await user.click(screen.getByRole("button", { name: "Confirm email" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Your email is confirmed.");
    expect(calls.at(-1)?.body).toEqual({ token: "tok2", password: "a-long-password" });
  });

  it("offers a fresh link when the token is not valid", async () => {
    setLocation("/verify-email#token=stale");
    const calls = stubApi({
      "POST /api/v1/auth/verify-email": errorResponse(
        "invalid_token",
        "This link is not valid or has expired.",
        400,
      ),
      "POST /api/v1/auth/verify-email/resend": { message: "Check your inbox." },
    });
    const user = userEvent.setup();

    render(<VerifyEmail />);
    expect(await screen.findByRole("alert")).toHaveTextContent("This link is not valid");

    await user.type(screen.getByLabelText("Email"), "me@example.com");
    await user.click(screen.getByRole("button", { name: "Send a new confirmation email" }));

    expect(calls.at(-1)).toMatchObject({
      path: "/api/v1/auth/verify-email/resend",
      body: { email: "me@example.com" },
    });
  });
});
