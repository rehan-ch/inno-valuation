// /api/v1/me: the signed-in user's account, active organisation and consultant access.
import { getJson, patchJson, postJson } from "./client";
import type { ConsultantAccessOut, MeOut, MessageOut } from "./types";

export function getMe(init?: RequestInit): Promise<MeOut> {
  return getJson("/me", init);
}

export function updateName(name: string): Promise<MeOut> {
  return patchJson("/me", { name });
}

export function setActiveOrganisation(organisationId: string): Promise<MeOut> {
  return postJson("/me/active-organisation", { organisation_id: organisationId });
}

export function changePassword(currentPassword: string, newPassword: string): Promise<MessageOut> {
  return postJson("/me/password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
}

export function listConsultantAccess(init?: RequestInit): Promise<ConsultantAccessOut[]> {
  return getJson("/me/consultant-access", init);
}

export function acceptConsultantAccess(grantId: string): Promise<ConsultantAccessOut> {
  return postJson(`/me/consultant-access/${grantId}/accept`);
}
