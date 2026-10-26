"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { FormEvent } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/fields";
import { resendVerification, signIn } from "@/lib/api/auth";
import type { MeOut } from "@/lib/api/types";
import { useSubmit } from "@/lib/forms";
import { safeNextFromLocation } from "@/lib/next-param";

function landingPage(me: MeOut): string {
  if (me.memberships.length > 0) return "/dashboard";
  if (me.consultant_organisations.length > 0) return "/consultant-access";
  return "/organisations/new";
}

export function SignInForm() {
  const router = useRouter();
  const { busy, error, run } = useSubmit();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<{ email?: string; password?: string }>({});
  const [resent, setResent] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setResent(false);
    const invalid = {
      email: email.trim() ? undefined : "Enter your email address.",
      password: password ? undefined : "Enter your password.",
    };
    if (invalid.email || invalid.password) {
      setFieldErrors(invalid);
      return;
    }
    const me = await run(() => signIn(email, password));
    // The hash (e.g. an invitation token) never reaches the server; carry it along.
    if (me) router.push((safeNextFromLocation() ?? landingPage(me)) + window.location.hash);
  }

  async function handleResend() {
    const sent = await run(() => resendVerification(email));
    if (sent) setResent(true);
  }

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4" noValidate>
      <h1 className="text-lg font-semibold text-neutral-900">Sign in</h1>
      {error && (
        <Alert tone="error">
          {error.message}
          {error.code === "email_not_verified" && (
            <span className="mt-2 block">
              <Button variant="secondary" busy={busy} onClick={() => void handleResend()}>
                Send the confirmation email again
              </Button>
            </span>
          )}
        </Alert>
      )}
      {resent && <Alert tone="success">Check your inbox for the confirmation email.</Alert>}
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
        autoComplete="current-password"
        required
        error={fieldErrors.password}
        value={password}
        onChange={(e) => {
          setPassword(e.target.value);
          setFieldErrors((prev) => ({ ...prev, password: undefined }));
        }}
      />
      <Button type="submit" busy={busy} className="w-full">
        Sign in
      </Button>
      <div className="flex justify-between gap-4 text-sm">
        <Link href="/forgot-password" className="font-medium text-primary hover:underline">
          Forgot your password?
        </Link>
        <Link href="/sign-up" className="font-medium text-primary hover:underline">
          Create an account
        </Link>
      </div>
    </form>
  );
}
