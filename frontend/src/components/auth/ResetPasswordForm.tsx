
"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";

import { AuthInput } from "@/components/auth/AuthInput";
import {
  authButtonClass,
  authSecondaryLinkClass,
} from "@/components/auth/authStyles";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { resetPassword } from "@/lib/api/auth";
import { clearHash, readHashToken } from "@/lib/hash-token";
import { newPasswordError, useSubmit } from "@/lib/forms";

export function ResetPasswordForm() {
  const { busy, error, run } = useSubmit();

  const [state, setState] = useState<
    "checking" | { token: string | null }
  >("checking");

  const [password, setPassword] = useState("");

  const [fieldError, setFieldError] =
    useState<string | undefined>();

  const [doneMessage, setDoneMessage] =
    useState<string | null>(null);

  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;

    started.current = true;

    setState({ token: readHashToken() });
    clearHash();
  }, []);

  const token =
    state === "checking" ? null : state.token;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();

    if (!token) return;

    const invalid = newPasswordError(password);

    if (invalid) {
      setFieldError(invalid);
      return;
    }

    const result = await run(() =>
      resetPassword(token, password),
    );

    if (result) {
      setDoneMessage(result.message);
    }
  }

  if (state === "checking") {
    return (
      <div
        role="status"
        className="py-5 text-sm text-slate-500"
      >
        Checking your reset link...
      </div>
    );
  }

  if (doneMessage) {
    return (
      <div className="space-y-5">
        <div className="flex size-14 items-center justify-center rounded-2xl border border-emerald-100 bg-emerald-50 text-emerald-700">
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
            <circle cx="12" cy="12" r="9" />
            <path d="m8 12 3 3 5-6" />
          </svg>
        </div>

        <h2 className="text-xl font-semibold text-[#10243B]">
          Password updated
        </h2>

        <Alert tone="success">
          {doneMessage}
        </Alert>

        <p className="text-sm leading-6 text-slate-600">
          Your password has been changed successfully.
          You can now sign in with your new password.
        </p>

        <Link
          href="/sign-in"
          className={authButtonClass}
        >
          Go to sign in
        </Link>
      </div>
    );
  }

  if (!token) {
    return (
      <div className="space-y-5">
        <Alert tone="error">
          This reset link is missing or invalid.
          Please request a new password reset email.
        </Alert>

        <Link
          href="/forgot-password"
          className={authButtonClass}
        >
          Request a new link
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
        label="New password"
        type="password"
        name="new_password"
        autoComplete="new-password"
        placeholder="Enter your new password"
        required
        minLength={8}
        error={fieldError}
        value={password}
        onChange={(event) => {
          const next = event.target.value;

          setPassword(next);

          setFieldError((previous) =>
            previous
              ? newPasswordError(next)
              : undefined,
          );
        }}
      />

      <Button
        type="submit"
        busy={busy}
        className={authButtonClass}
      >
        {busy
          ? "Updating password..."
          : "Change password"}
      </Button>

      <div className="text-center">
        <Link
          href="/sign-in"
          className={authSecondaryLinkClass}
        >
          Back to sign in
        </Link>
      </div>
    </form>
  );
}
