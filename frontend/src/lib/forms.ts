"use client";

import { useRef, useState } from "react";

import { ApiError } from "@/lib/api/client";

// Client-side checks for the rules the backend enforces, so a mistake gets a
// field message instead of the API's generic "The request is not valid.".
// The shapes mirror backend/app/schemas/common.py.

const EMAIL_SHAPE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
export const PASSWORD_MIN_LENGTH = 10;

export function emailError(email: string): string | undefined {
  if (!email.trim()) return "Enter an email address.";
  if (!EMAIL_SHAPE.test(email)) return "Enter a full email address, like name@company.com.";
  return undefined;
}

export function newPasswordError(password: string): string | undefined {
  if (password.length < PASSWORD_MIN_LENGTH) return "Use at least 10 characters.";
  return undefined;
}

/** Runs one async action at a time and keeps its busy and error state for the form.
 * A call while one is still running returns undefined without starting the action. */
export function useSubmit() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  // The state lags a re-render behind, so a ref guards against double submits.
  const running = useRef(false);

  async function run<T>(action: () => Promise<T>): Promise<T | undefined> {
    if (running.current) return undefined;
    running.current = true;
    setBusy(true);
    setError(null);
    try {
      return await action();
    } catch (err) {
      setError(
        err instanceof ApiError ? err : new ApiError("unknown_error", "Something went wrong.", 0),
      );
      return undefined;
    } finally {
      running.current = false;
      setBusy(false);
    }
  }

  return { busy, error, run, clearError: () => setError(null) };
}
