
"use client";

import Link from "next/link";
import { useState } from "react";
import type { FormEvent } from "react";

import { AuthInput } from "@/components/auth/AuthInput";
import {
  authButtonClass,
  authSecondaryLinkClass,
} from "@/components/auth/authStyles";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { forgotPassword } from "@/lib/api/auth";
import { emailError, useSubmit } from "@/lib/forms";

export function ForgotPasswordForm() {
  const { busy, error, run } = useSubmit();

  const [email, setEmail] = useState("");
  const [fieldError, setFieldError] =
    useState<string | undefined>();

  const [sentMessage, setSentMessage] =
    useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();

    const invalid = emailError(email);

    if (invalid) {
      setFieldError(invalid);
      return;
    }

    const result = await run(() =>
      forgotPassword(email),
    );

    if (result) {
      setSentMessage(result.message);
    }
  }

  if (sentMessage) {
    return (
      <div className="space-y-5">
        <div className="flex size-14 items-center justify-center rounded-2xl border border-[#D6DFE9] bg-[#F3F6FA] text-[#10243B]">
          <svg
            className="size-7"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <rect x="3" y="5" width="18" height="14" rx="2" />
            <path d="m3 7 9 6 9-6" />
          </svg>
        </div>

        <h2 className="text-xl font-semibold text-[#10243B]">
          Check your inbox
        </h2>

        <Alert tone="success">
          {sentMessage}
        </Alert>

        <p className="text-sm leading-6 text-slate-600">
          If an account exists for this email address,
          follow the instructions in the reset email.
        </p>

        <Link
          href="/sign-in"
          className={authButtonClass}
        >
          Back to sign in
        </Link>
      </div>
    );
  }

  return (
    <form
      onSubmit={(event) => void handleSubmit(event)}
      className="space-y-5"
      noValidate
    >
      {error && (
        <Alert tone="error">
          {error.message}
        </Alert>
      )}

      <AuthInput
        label="Email address"
        type="email"
        name="email"
        autoComplete="email"
        placeholder="you@company.com"
        required
        error={fieldError}
        value={email}
        onChange={(event) => {
          setEmail(event.target.value);
          setFieldError(undefined);
        }}
      />

      <Button
        type="submit"
        busy={busy}
        className={authButtonClass}
      >
        {busy
          ? "Sending reset link..."
          : "Send reset link"}
      </Button>

      <div className="text-center">
        <Link
          href="/sign-in"
          className={authSecondaryLinkClass}
        >
          <span aria-hidden="true">←</span>
          Back to sign in
        </Link>
      </div>
    </form>
  );
}
