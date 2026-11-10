// /api/v1/dashboard and /api/v1/history: the two headline scores side by side, the compass,
// the dimension drill-down and the change over time. Every number, level, gap and change
// comes from the server; nothing is worked out here.
import { getJson } from "./client";
import type {
  DashboardOut,
  DimensionDetailOut,
  IdeaHistoryOut,
  ReadinessHistoryOut,
} from "./types";

function withIdea(path: string, ideaId?: string | null): string {
  return ideaId ? `${path}?idea_id=${encodeURIComponent(ideaId)}` : path;
}

/** Readiness (out of 300) and the selected idea's IQ (out of 100), never combined.
 * Without an idea the most recently confirmed one is selected. */
export function getDashboard(ideaId?: string | null): Promise<DashboardOut> {
  return getJson(withIdea("/dashboard", ideaId));
}

export function getDimension(key: string, ideaId?: string | null): Promise<DimensionDetailOut> {
  return getJson(withIdea(`/dashboard/dimensions/${encodeURIComponent(key)}`, ideaId));
}

export function getReadinessHistory(): Promise<ReadinessHistoryOut> {
  return getJson("/history/readiness");
}

export function getIdeaHistory(ideaId: string): Promise<IdeaHistoryOut> {
  return getJson(`/history/ideas/${ideaId}`);
}

/** Where a dimension's page lives, keeping the selected idea. */
export function dimensionHref(key: string, ideaId?: string | null): string {
  return withIdea(`/dimensions/${key}`, ideaId).replace("idea_id=", "idea=");
}
