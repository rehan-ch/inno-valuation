"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/fields";
import { resetPassword } from "@/lib/api/auth";
import { clearHash, readHashToken } from "@/lib/hash-token";
import { useSubmit } from "@/lib/forms";

export function ResetPasswordForm() {
  const { busy, error, run } = useSubmit();
  // "checking" until the fragment is read; then the token, or null when the link had none.
  const [state, setState] = useState<"checking" | { token: string | null }>("checking");
  const [password, setPassword] = useState("");
  const [doneMessage, setDoneMessage] = useState<string | null>(null);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time read of the URL fragment, only possible after mount
    setState({ token: readHashToken() });
    clearHash();
  }, []);

  const token = state === "checking" ? null : state.token;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!token) return;
    const result = await run(() => resetPassword(token, password));
    if (result) setDoneMessage(result.message);
  }

  if (state === "checking") return null;

  if (doneMessage) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-semibold text-neutral-900">Password changed</h1>
        <Alert tone="success">{doneMessage}</Alert>
        <p className="text-sm">
          <Link href="/sign-in" className="underline">
            Go to sign in
          </Link>
        </p>
      </div>
    );
  }

  if (!token) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-semibold text-neutral-900">Reset your password</h1>
        <Alert tone="error">
          This page needs the link from the password reset email.{" "}
          <Link href="/forgot-password" className="underline">
            Request a new link
          </Link>
          .
        </Alert>
      </div>
    );
  }

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4" noValidate>
      <h1 className="text-xl font-semibold text-neutral-900">Choose a new password</h1>
      {error && <Alert tone="error">{error.message}</Alert>}
      <TextField
        label="New password"
        type="password"
        name="new_password"
        autoComplete="new-password"
        required
        minLength={10}
        hint="At least 10 characters."
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <Button type="submit" busy={busy} className="w-full">
        Change password
      </Button>
    </form>
  );
}
