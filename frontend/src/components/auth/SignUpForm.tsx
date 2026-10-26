"use client";

import Link from "next/link";
import { useState } from "react";
import type { FormEvent } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { CheckboxField, TextField } from "@/components/ui/fields";
import { signUp } from "@/lib/api/auth";
import { emailError, newPasswordError, useSubmit } from "@/lib/forms";

interface FieldErrors {
  name?: string;
  email?: string;
  password?: string;
}

export function SignUpForm() {
  const { busy, error, run } = useSubmit();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [accepted, setAccepted] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [sentMessage, setSentMessage] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!accepted) return;
    const invalid: FieldErrors = {
      name: name.trim() ? undefined : "Enter your name.",
      email: emailError(email),
      password: newPasswordError(password),
    };
    if (invalid.name || invalid.email || invalid.password) {
      setFieldErrors(invalid);
      return;
    }
    const result = await run(() => signUp({ name, email, password, accepted_terms: true }));
    if (result) setSentMessage(result.message);
  }

  if (sentMessage) {
    return (
      <div className="space-y-4">
        <h1 className="text-lg font-semibold text-neutral-900">Check your inbox</h1>
        <Alert tone="success">{sentMessage}</Alert>
        <p className="text-sm text-neutral-600">
          Open the link in the email to confirm your address, then{" "}
          <Link href="/sign-in" className="font-medium text-primary hover:underline">
            sign in
          </Link>
          .
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4" noValidate>
      <h1 className="text-lg font-semibold text-neutral-900">Create an account</h1>
      {error && <Alert tone="error">{error.message}</Alert>}
      <TextField
        label="Name"
        name="name"
        autoComplete="name"
        required
        error={fieldErrors.name}
        value={name}
        onChange={(e) => {
          setName(e.target.value);
          setFieldErrors((prev) => ({ ...prev, name: undefined }));
        }}
      />
      <TextField
        label="Email"
        type="email"
        name="email"
        autoComplete="email"
        required
        error={fieldErrors.email}
        value={email}
        onChange={(e) => {
          setEmail(e.target.value);
          setFieldErrors((prev) => ({ ...prev, email: undefined }));
        }}
      />
      <TextField
        label="Password"
        type="password"
        name="password"
        autoComplete="new-password"
        required
        minLength={8}
        error={fieldErrors.password}
        value={password}
        onChange={(e) => {
          const next = e.target.value;
          setPassword(next);
          // Once shown, the length message stays until the password reaches 8.
          setFieldErrors((prev) =>
            prev.password ? { ...prev, password: newPasswordError(next) } : prev,
          );
        }}
      />
      <CheckboxField
        label="I accept the terms of service and the privacy policy."
        name="accepted_terms"
        required
        checked={accepted}
        onChange={(e) => setAccepted(e.target.checked)}
      />
      <Button type="submit" busy={busy} disabled={!accepted} className="w-full">
        Create account
      </Button>
      <p className="text-sm">
        Already have an account?{" "}
        <Link href="/sign-in" className="font-medium text-primary hover:underline">
          Sign in
        </Link>
      </p>
    </form>
  );
}
