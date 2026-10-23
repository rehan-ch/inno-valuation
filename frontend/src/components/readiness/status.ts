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
