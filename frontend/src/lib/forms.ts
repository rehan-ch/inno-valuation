"use client";

import { useState } from "react";

import { ApiError } from "@/lib/api/client";

/** Runs one async action at a time and keeps its busy and error state for the form. */
export function useSubmit() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  async function run<T>(action: () => Promise<T>): Promise<T | undefined> {
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
      setBusy(false);
    }
  }

  return { busy, error, run, clearError: () => setError(null) };
}
