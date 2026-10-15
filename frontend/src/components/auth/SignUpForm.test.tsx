import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { stubApi } from "@/test/api";

import { SignUpForm } from "./SignUpForm";

describe("SignUpForm", () => {
  it("signs up with accepted terms and shows the check-inbox message", async () => {
    const calls = stubApi({
      "POST /api/v1/auth/sign-up": { message: "Check your inbox." },
    });
    const user = userEvent.setup();

    render(<SignUpForm />);
    await user.type(screen.getByLabelText("Name"), "New Person");
    await user.type(screen.getByLabelText("Email"), "new@example.com");
    await user.type(screen.getByLabelText("Password"), "a-long-password");
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(calls[0]?.body).toEqual({
      name: "New Person",
      email: "new@example.com",
      password: "a-long-password",
      accepted_terms: true,
    });
    expect(await screen.findByRole("status")).toHaveTextContent("Check your inbox.");
  });

  it("does not submit until the terms are accepted", async () => {
    const calls = stubApi({});

    render(<SignUpForm />);
    expect(screen.getByRole("button", { name: "Create account" })).toBeDisabled();
    expect(calls).toHaveLength(0);
  });
});
