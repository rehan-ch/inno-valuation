
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { FormEvent } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { AuthInput } from "@/components/auth/AuthInput";
import { resendVerification, signIn } from "@/lib/api/auth";
import type { MeOut } from "@/lib/api/types";
import { useSubmit } from "@/lib/forms";
import { safeNextFromLocation } from "@/lib/next-param";

function landingPage(me: MeOut): string {
  if (me.memberships.length > 0) return "/dashboard";

  if (me.consultant_organisations.length > 0) {
    return "/consultant-access";
  }

  return "/organisations/new";
}

const actionClass = [
  "group relative flex h-12 w-full items-center justify-center",
  "!rounded-xl !bg-[#10243B] !text-white",
  "!shadow-[0_6px_18px_rgba(16,36,59,0.12)]",
  "transition-all duration-200",
  "hover:!bg-[#1B3452]",
  "hover:!shadow-[0_9px_22px_rgba(16,36,59,0.17)]",
  "active:scale-[0.99]",
  "focus-visible:!outline-[#304E73]",
  "disabled:!bg-[#8797A9] disabled:!shadow-none",
  "motion-reduce:transform-none",
].join(" ");

const linkClass = [
  "font-semibold text-[#183C64]",
  "transition-colors duration-200",
  "hover:text-[#315D89] hover:underline",
  "focus-visible:rounded-sm",
  "focus-visible:outline-2",
  "focus-visible:outline-offset-2",
  "focus-visible:outline-[#315D89]",
].join(" ");

export function SignInForm() {
  const router = useRouter();
  const { busy, error, run } = useSubmit();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [fieldErrors, setFieldErrors] = useState<{
    email?: string;
    password?: string;
  }>({});

  const [resent, setResent] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setResent(false);

    const invalid = {
      email: email.trim()
        ? undefined
        : "Enter your email address.",
      password: password
        ? undefined
        : "Enter your password.",
    };

    if (invalid.email || invalid.password) {
      setFieldErrors(invalid);
      return;
    }

    const me = await run(() => signIn(email, password));

    if (me) {
      // Preserve invitation fragments during redirects.
      router.push(
        (safeNextFromLocation() ?? landingPage(me)) +
        window.location.hash,
      );
    }
  }

  async function handleResend() {
    const sent = await run(() =>
      resendVerification(email),
    );

    if (sent) setResent(true);
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

          {error.code === "email_not_verified" && (
            <span className="mt-3 block">
              <Button
                variant="secondary"
                busy={busy}
                onClick={() => void handleResend()}
              >
                Send the confirmation email again
              </Button>
            </span>
          )}
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

      <div>
        <AuthInput
          label="Password"
          type="password"
          name="password"
          autoComplete="current-password"
          placeholder="Enter your password"
          required
          error={fieldErrors.password}
          value={password}
          onChange={(event) => {
            setPassword(event.target.value);
            setFieldErrors((previous) => ({
              ...previous,
              password: undefined,
            }));
          }}
        />

        <div className="mt-2 flex justify-end">
          <Link
            href="/forgot-password"
            className={`text-xs ${linkClass}`}
          >
            Forgot password?
          </Link>
        </div>
      </div>

      <Button
        type="submit"
        busy={busy}
        className={actionClass}
      >
        {busy ? (
          <span className="flex items-center gap-2">
            <svg
              className="size-4 animate-spin motion-reduce:animate-none"
              viewBox="0 0 24 24"
              fill="none"
              aria-hidden="true"
            >
              <circle
                cx="12"
                cy="12"
                r="9"
                stroke="currentColor"
                strokeWidth="3"
                className="opacity-25"
              />
              <path
                d="M12 3a9 9 0 0 1 9 9"
                stroke="currentColor"
                strokeWidth="3"
                strokeLinecap="round"
              />
            </svg>
            Signing in...
          </span>
        ) : (
          <span className="flex items-center gap-2">
            Sign in to workspace
            <svg
              className="size-4 transition-transform duration-200 group-hover:translate-x-1 motion-reduce:transform-none"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M5 12h14M13 6l6 6-6 6" />
            </svg>
          </span>
        )}
      </Button>

      <p className="pt-1 text-center text-sm text-slate-500">
        New to InnoValuation?{" "}
        <Link href="/sign-up" className={linkClass}>
          Create an account
        </Link>
      </p>
    </form>
  );
}
