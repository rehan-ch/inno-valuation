import { ApiError } from "@/lib/api/client";
import type { ReadinessStatus } from "@/lib/api/types";

export const STATUS_LABELS: Record<ReadinessStatus, string> = {
  draft: "Draft",
  collecting: "Collecting answers",
  consensus: "Agreeing answers",
  final: "Final",
};

export const STATUS_TONES: Record<ReadinessStatus, "neutral" | "amber" | "green"> = {
  draft: "neutral",
  collecting: "amber",
  consensus: "amber",
  final: "green",
};

export const MY_STATUS_LABELS = {
  not_started: "You have not started",
  in_progress: "Your answers are in progress",
  submitted: "You have submitted your answers",
} as const;

/** Why an autosave failed, in plain words. A lost session or missing permission is not
 * a connection problem, so only a network failure asks about the connection. */
export function saveFailureMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return "Not saved. Your session has ended: sign in again to carry on.";
    if (err.status === 403) return "Not saved. You do not have permission to change this.";
    if (err.status === 0) return "Not saved. Check your connection and choose again.";
    return `Not saved. ${err.message}`;
  }
  return "Not saved. Something went wrong; choose again.";
}
