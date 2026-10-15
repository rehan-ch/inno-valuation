import type { MembershipRole, MeOut, OrgRole } from "@/lib/api/types";

/** Roles in display order, with the words the app uses for them. */
export const ROLE_LABELS: Record<MembershipRole, string> = {
  owner: "Owner",
  admin: "Admin",
  member: "Member",
  committee: "Committee member",
  investor: "Investor",
};

export const MEMBERSHIP_ROLES = Object.keys(ROLE_LABELS) as MembershipRole[];

export function roleLabel(role: MembershipRole | OrgRole): string {
  return role === "consultant" ? "Consultant" : ROLE_LABELS[role];
}

/** "an owner", "a member", ... for sentences; mirrors the wording in the backend emails. */
export function roleWithArticle(role: MembershipRole): string {
  const label = ROLE_LABELS[role].toLowerCase();
  return `${/^[aeiou]/.test(label) ? "an" : "a"} ${label}`;
}

/** Owners and admins manage the team and consultant access (mirrors the backend matrix). */
export function canManage(role: OrgRole | MembershipRole): boolean {
  return role === "owner" || role === "admin";
}

/** Roles the actor may give out: only an owner can give the owner role. */
export function assignableRoles(actorRole: OrgRole): MembershipRole[] {
  return MEMBERSHIP_ROLES.filter((role) => role !== "owner" || actorRole === "owner");
}

export function activeMembership(me: MeOut) {
  return me.memberships.find((m) => m.organisation_id === me.active_organisation_id) ?? null;
}
