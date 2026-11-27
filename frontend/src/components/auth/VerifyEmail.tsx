
"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";

import { AuthInput } from "@/components/auth/AuthInput";
import { authButtonClass } from "@/components/auth/authStyles";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Loading } from "@/components/ui/Loading";
import { resendVerification, verifyEmail } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import { clearHash, readHashToken } from "@/lib/hash-token";
import { newPasswordError, useSubmit } from "@/lib/forms";

type State =
  | { kind: "checking" }
  | { kind: "no_token" }
  | { kind: "needs_password"; token: string }
  | { kind: "failed"; message: string }
  | { kind: "done"; message: string };

export function VerifyEmail() {
  const [state, setState] = useState<State>({
    kind: "checking",
  });

  const { busy, error, run } = useSubmit();

  const [password, setPassword] = useState("");
  const [passwordError, setPasswordError] =
    useState<string | undefined>();

  const [email, setEmail] = useState("");
  const [resent, setResent] = useState(false);

  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;

    started.current = true;

    const token = readHashToken();
    clearHash();

    if (!token) {
      queueMicrotask(() => {
        setState({ kind: "no_token" });
      });
      return;
    }

    verifyEmail({ token })
      .then((result) =>
        setState({
          kind: "done",
          message: result.message,
        }),
      )
      .catch((err: unknown) => {
        if (
          err instanceof ApiError &&
          err.code === "password_required"
        ) {
          setState({
            kind: "needs_password",
            token,
          });
        } else {
          setState({
            kind: "failed",
            message:
              err instanceof ApiError
                ? err.message
                : "Something went wrong.",
          });
        }
      });
  }, []);

  async function submitPassword(
    event: FormEvent,
    token: string,
  ) {
    event.preventDefault();

    const invalid = newPasswordError(password);

    if (invalid) {
      setPasswordError(invalid);
      return;
    }

    const result = await run(() =>
      verifyEmail({ token, password }),
    );

    if (result) {
      setState({
        kind: "done",
        message: result.message,
      });
    }
  }

  async function submitResend(event: FormEvent) {
    event.preventDefault();

    const sent = await run(() =>
      resendVerification(email),
    );

    if (sent) setResent(true);
  }

  if (state.kind === "checking") {
    return <Loading>Confirming your email...</Loading>;
  }

  if (state.kind === "done") {
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
          Email confirmed
        </h2>

        <Alert tone="success">
          {state.message}
        </Alert>

        <p className="text-sm leading-6 text-slate-600">
          Your email is confirmed. Continue to your
          innovation workspace.
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

  if (state.kind === "needs_password") {
    return (
      <form
        onSubmit={(event) =>
          void submitPassword(event, state.token)
        }
        className="space-y-5"
        noValidate
      >
        <h2 className="text-lg font-semibold text-[#10243B]">
          Choose a password
        </h2>

        <p className="text-sm leading-6 text-slate-600">
          Create a password to finish setting up
          your account.
        </p>

        {error && (
          <Alert tone="error">
            {error.message}
          </Alert>
        )}

        <AuthInput
          label="New password"
          type="password"
          name="password"
          autoComplete="new-password"
          placeholder="Create a secure password"
          required
          minLength={8}
          error={passwordError}
          value={password}
          onChange={(event) => {
            const next = event.target.value;

            setPassword(next);

            setPasswordError((previous) =>
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
            ? "Confirming..."
            : "Confirm email"}
        </Button>
      </form>
    );
  }

  return (
    <form
      onSubmit={(event) => void submitResend(event)}
      className="space-y-5"
      noValidate
    >
      <h2 className="text-lg font-semibold text-[#10243B]">
        Confirm your email
      </h2>

      {state.kind === "failed" && (
        <Alert tone="error">
          {state.message}
        </Alert>
      )}

      {state.kind === "no_token" && (
        <p className="text-sm leading-6 text-slate-600">
          This page needs the link from your confirmation
          email. Enter your email address to request a new one.
        </p>
      )}

      {error && (
        <Alert tone="error">
          {error.message}
        </Alert>
      )}

      {resent && (
        <Alert tone="success">
          Check your inbox for the confirmation email.
        </Alert>
      )}

      <AuthInput
        label="Email address"
        type="email"
        name="email"
        autoComplete="email"
        placeholder="you@company.com"
        required
        value={email}
        onChange={(event) =>
          setEmail(event.target.value)
        }
      />

      <Button
        type="submit"
        busy={busy}
        className={authButtonClass}
      >
        {busy
          ? "Sending confirmation..."
          : "Send a new confirmation email"}
      </Button>
    </form>
  );
}
