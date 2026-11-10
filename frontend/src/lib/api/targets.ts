// /api/v1/targets: the score the organisation wants to reach per dimension, on each scale.
// A target changes no score; the gap to it is shown with each result.
import { getJson, putJson } from "./client";
import type { TargetScale, TargetsChangeOut, TargetsOut } from "./types";

const BASE = "/targets";

export function getTargets(): Promise<TargetsOut> {
  return getJson(BASE);
}

export function getTargetsHistory(): Promise<TargetsChangeOut[]> {
  return getJson(`${BASE}/history`);
}

/** Replace one scale's targets. A dimension left out, or null, has no target. */
export function setTargets(
  scale: TargetScale,
  targets: Record<string, number | null>,
): Promise<TargetsOut> {
  return putJson(`${BASE}/${scale}`, { targets });
}
