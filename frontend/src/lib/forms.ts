"use client";

import { useRef, useState } from "react";

import { ApiError } from "@/lib/api/client";

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
