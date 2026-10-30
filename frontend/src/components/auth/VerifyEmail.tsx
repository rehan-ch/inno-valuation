"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/fields";
import { resendVerification, verifyEmail } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import { Loading } from "@/components/ui/Loading";
import { clearHash, readHashToken } from "@/lib/hash-token";
import { newPasswordError, useSubmit } from "@/lib/forms";

type State =
  | { kind: "checking" }
  | { kind: "no_token" }
  | { kind: "needs_password"; token: string }
  | { kind: "failed"; message: string }
  | { kind: "done"; message: string };

export function VerifyEmail() {
  const [state, setState] = useState<State>({ kind: "checking" });
  const { busy, error, run } = useSubmit();
  const [password, setPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | undefined>(undefined);
  const [email, setEmail] = useState("");
  const [resent, setResent] = useState(false);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return; // React strict mode mounts twice; verify only once.
    started.current = true;
    const token = readHashToken();
    clearHash();
    if (!token) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time read of the URL fragment, only possible after mount
      setState({ kind: "no_token" });
      return;
    }
    verifyEmail({ token })
      .then((result) => setState({ kind: "done", message: result.message }))
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.code === "password_required") {
          setState({ kind: "needs_password", token });
        } else {
          setState({
            kind: "failed",
            message: err instanceof ApiError ? err.message : "Something went wrong.",
          });
        }
      });
  }, []);

  async function submitPassword(event: FormEvent, token: string) {
    event.preventDefault();
    const invalid = newPasswordError(password);
    if (invalid) {
      setPasswordError(invalid);
      return;
    }
    const result = await run(() => verifyEmail({ token, password }));
    if (result) setState({ kind: "done", message: result.message });
  }

  async function submitResend(event: FormEvent) {
    event.preventDefault();
    const sent = await run(() => resendVerification(email));
    if (sent) setResent(true);
  }

  if (state.kind === "checking") {
    return <Loading>Confirming your email...</Loading>;
  }

  if (state.kind === "done") {
    return (
      <div className="space-y-4">
        <h1 className="text-lg font-semibold text-neutral-900">Email confirmed</h1>
        <Alert tone="success">{state.message}</Alert>
        <p className="text-sm">
          <Link href="/sign-in" className="font-medium text-primary hover:underline">
            Go to sign in
          </Link>
        </p>
      </div>
    );
  }

  if (state.kind === "needs_password") {
    return (
      <form onSubmit={(e) => void submitPassword(e, state.token)} className="space-y-4" noValidate>
        <h1 className="text-lg font-semibold text-neutral-900">Choose a password</h1>
        <p className="text-sm text-neutral-600">
          Choose a password to finish setting up your account.
        </p>
        {error && <Alert tone="error">{error.message}</Alert>}
        <TextField
          label="New password"
          type="password"
          name="password"
          autoComplete="new-password"
          required
          minLength={8}
          error={passwordError}
          value={password}
          onChange={(e) => {
            const next = e.target.value;
            setPassword(next);
            // Once shown, the length message stays until the password reaches 8.
            setPasswordError((prev) => (prev ? newPasswordError(next) : undefined));
          }}
        />
        <Button type="submit" busy={busy} className="w-full">
          Confirm email
        </Button>
      </form>
    );
  }

  // no_token or failed: offer to send a fresh link.
  return (
    <form onSubmit={(e) => void submitResend(e)} className="space-y-4" noValidate>
      <h1 className="text-lg font-semibold text-neutral-900">Confirm your email</h1>
      {state.kind === "failed" && <Alert tone="error">{state.message}</Alert>}
      {state.kind === "no_token" && (
        <p className="text-sm text-neutral-600">
          This page needs the link from your confirmation email. Enter your email address and we
          will send a fresh one.
        </p>
      )}
      {error && <Alert tone="error">{error.message}</Alert>}
      {resent && <Alert tone="success">Check your inbox for the confirmation email.</Alert>}
      <TextField
        label="Email"
        type="email"
        name="email"
        autoComplete="email"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />
      <Button type="submit" busy={busy} className="w-full">
        Send a new confirmation email
      </Button>
    </form>
  );
}
