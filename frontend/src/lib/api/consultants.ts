// /api/v1/organisation/consultants: consultant access to the active organisation,
// managed by its owners and admins.
import { deleteJson, getJson, patchJson, postJson } from "./client";
import type { ConsultantGrantOut } from "./types";

export function listGrants(init?: RequestInit): Promise<ConsultantGrantOut[]> {
  return getJson("/organisation/consultants", init);
}

export function grantAccess(email: string, expiresAt: string): Promise<ConsultantGrantOut> {
  return postJson("/organisation/consultants", { email, expires_at: expiresAt });
}

export function changeGrantEndDate(grantId: string, expiresAt: string): Promise<ConsultantGrantOut> {
  return patchJson(`/organisation/consultants/${grantId}`, { expires_at: expiresAt });
}

export function revokeGrant(grantId: string): Promise<ConsultantGrantOut> {
  return deleteJson(`/organisation/consultants/${grantId}`);
}
