// /api/v1/weights: the active organisation's dimension importance. Weights never change a
// score or the IQ; they only order tied priorities.
import { getJson, postJson, putJson } from "./client";
import type { WeightsChangeOut, WeightsIn, WeightsOut } from "./types";

const BASE = "/weights";

export function getWeights(init?: RequestInit): Promise<WeightsOut> {
  return getJson(BASE, init);
}

export function getWeightsHistory(
  init?: RequestInit,
): Promise<WeightsChangeOut[]> {
  return getJson(`${BASE}/history`, init);
}

/** Replace every dimension's weight. Decimal strings, so no float ever touches a weight. */
export function setWeights(input: WeightsIn): Promise<WeightsOut> {
  return putJson(BASE, input);
}

export function resetWeights(): Promise<WeightsOut> {
  return postJson(`${BASE}/reset`);
}
