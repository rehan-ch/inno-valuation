"use client";

import Link from "next/link";
import { useState } from "react";
import type { FormEvent } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/fields";
import { forgotPassword } from "@/lib/api/auth";
import { emailError, useSubmit } from "@/lib/forms";

export function ForgotPasswordForm() {
  const { busy, error, run } = useSubmit();
  const [email, setEmail] = useState("");
  const [fieldError, setFieldError] = useState<string | undefined>(undefined);
  const [sentMessage, setSentMessage] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const invalid = emailError(email);
    if (invalid) {
      setFieldError(invalid);
      return;
    }
    const result = await run(() => forgotPassword(email));
    if (result) setSentMessage(result.message);
  }

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4" noValidate>
      <h1 className="text-lg font-semibold text-neutral-900">Forgot your password?</h1>
      <p className="text-sm text-neutral-600">
        Enter your email address and we will send you a link to choose a new password.
      </p>
      {error && <Alert tone="error">{error.message}</Alert>}
      {sentMessage && <Alert tone="success">{sentMessage}</Alert>}
      <TextField
        label="Email"
        type="email"
        name="email"
        autoComplete="email"
        required
        error={fieldError}
        value={email}
        onChange={(e) => {
          setEmail(e.target.value);
          setFieldError(undefined);
        }}
      />
      <Button type="submit" busy={busy} className="w-full">
        Send reset link
      </Button>
      <p className="text-sm">
        <Link href="/sign-in" className="font-medium text-primary hover:underline">
          Back to sign in
        </Link>
      </p>
    </form>
  );
}
