
"use client";

import Link from "next/link";
import { useState } from "react";
import type { FormEvent } from "react";

import { AuthInput } from "@/components/auth/AuthInput";
import {
  authButtonClass,
  authLinkClass,
} from "@/components/auth/authStyles";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { signUp } from "@/lib/api/auth";
import {
  emailError,
  newPasswordError,
  useSubmit,
} from "@/lib/forms";

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

  const [fieldErrors, setFieldErrors] =
    useState<FieldErrors>({});

  const [sentMessage, setSentMessage] =
    useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();

    if (!accepted) return;

    const invalid: FieldErrors = {
      name: name.trim()
        ? undefined
        : "Enter your name.",
      email: emailError(email),
      password: newPasswordError(password),
    };

    if (
      invalid.name ||
      invalid.email ||
      invalid.password
    ) {
      setFieldErrors(invalid);
      return;
    }

    const result = await run(() =>
      signUp({
        name,
        email,
        password,
        accepted_terms: true,
      }),
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
          Open the confirmation link in your email to
          activate your account.
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

  return (
    <form
      onSubmit={(event) => void handleSubmit(event)}
      className="space-y-4"
      noValidate
    >
      {error && (
        <Alert tone="error">
          {error.message}
        </Alert>
      )}

      <AuthInput
        label="Full name"
        type="text"
        name="name"
        autoComplete="name"
        placeholder="Enter your full name"
        required
        error={fieldErrors.name}
        value={name}
        onChange={(event) => {
          setName(event.target.value);

          setFieldErrors((previous) => ({
            ...previous,
            name: undefined,
          }));
        }}
      />

      <AuthInput
        label="Email address"
        type="email"
        name="email"
        autoComplete="email"
        placeholder="you@company.com"
        required
        error={fieldErrors.email}
        value={email}
        onChange={(event) => {
          setEmail(event.target.value);

          setFieldErrors((previous) => ({
            ...previous,
            email: undefined,
          }));
        }}
      />

      <AuthInput
        label="Create password"
        type="password"
        name="password"
        autoComplete="new-password"
        placeholder="Create a secure password"
        required
        minLength={8}
        error={fieldErrors.password}
        value={password}
        onChange={(event) => {
          const next = event.target.value;
          setPassword(next);

          setFieldErrors((previous) => ({
            ...previous,
            password: previous.password
              ? newPasswordError(next)
              : undefined,
          }));
        }}
      />

      <div className="flex items-start gap-3">
        <input
          id="auth-accepted-terms"
          type="checkbox"
          name="accepted_terms"
          required
          checked={accepted}
          onChange={(event) =>
            setAccepted(event.target.checked)
          }
          className="mt-1 size-4 shrink-0 cursor-pointer rounded border-[#AEBCCB] accent-[#10243B] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#304E73]"
        />

        <label
          htmlFor="auth-accepted-terms"
          className="text-xs leading-6 text-[#52677D]"
        >
          I accept the terms of service and the privacy policy.
        </label>
      </div>

      <Button
        type="submit"
        busy={busy}
        disabled={!accepted}
        className={authButtonClass}
      >
        {busy
          ? "Creating account..."
          : "Create your account"}
      </Button>

      <p className="pt-1 text-center text-sm text-slate-500">
        Already have an account?{" "}
        <Link
          href="/sign-in"
          className={authLinkClass}
        >
          Sign in
        </Link>
      </p>
    </form>
  );
}
