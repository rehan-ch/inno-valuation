// /api/v1/organisation/members and /invitations: the active organisation's team,
// plus /api/v1/invitations: the invited person's side (preview and accept).
import { deleteJson, getJson, patchJson, postJson } from "./client";
import type {
  InvitationOut,
  InvitationPreviewOut,
  MemberOut,
  MembershipRole,
  MeOut,
  MessageOut,
} from "./types";

export function listMembers(init?: RequestInit): Promise<MemberOut[]> {
  return getJson("/organisation/members", init);
}

export function changeMemberRole(membershipId: string, role: MembershipRole): Promise<MemberOut> {
  return patchJson(`/organisation/members/${membershipId}`, { role });
}

export function removeMember(membershipId: string): Promise<MessageOut> {
  return deleteJson(`/organisation/members/${membershipId}`);
}

export function listInvitations(init?: RequestInit): Promise<InvitationOut[]> {
  return getJson("/organisation/invitations", init);
}

export function sendInvitation(email: string, role: MembershipRole): Promise<InvitationOut> {
  return postJson("/organisation/invitations", { email, role });
}

export function cancelInvitation(invitationId: string): Promise<MessageOut> {
  return deleteJson(`/organisation/invitations/${invitationId}`);
}

export function previewInvitation(token: string): Promise<InvitationPreviewOut> {
  return postJson("/invitations/preview", { token });
}

export function acceptInvitation(token: string): Promise<MeOut> {
  return postJson("/invitations/accept", { token });
}
