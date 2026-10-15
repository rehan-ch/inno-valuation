"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import { useMe } from "@/components/app/me-context";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardTitle, PageHeader } from "@/components/ui/Card";
import { ConfirmButton } from "@/components/ui/ConfirmButton";
import { SelectField, TextField } from "@/components/ui/fields";
import { Loading } from "@/components/ui/Loading";
import { ApiError } from "@/lib/api/client";
import { getOrganisation } from "@/lib/api/organisation";
import {
  cancelInvitation,
  changeMemberRole,
  listInvitations,
  listMembers,
  removeMember,
  sendInvitation,
} from "@/lib/api/team";
import type {
  InvitationOut,
  MemberOut,
  MembershipRole,
  OrganisationOut,
} from "@/lib/api/types";
import { formatDate } from "@/lib/format";
import { useSubmit } from "@/lib/forms";
import { assignableRoles, canManage, roleLabel } from "@/lib/roles";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | {
      kind: "ready";
      org: OrganisationOut;
      members: MemberOut[];
      invitations: InvitationOut[];
    };

export function TeamPage() {
  const { me } = useMe();
  const activeOrgId = me.active_organisation_id;
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    if (!activeOrgId) return;
    let cancelled = false;
    async function load() {
      setState({ kind: "loading" });
      try {
        const org = await getOrganisation();
        const members = org.role === "consultant" ? [] : await listMembers();
        const manage = canManage(org.role) && org.status === "active";
        const invitations = manage ? await listInvitations() : [];
        if (!cancelled) setState({ kind: "ready", org, members, invitations });
      } catch (err) {
        if (!cancelled) {
          setState({
            kind: "error",
            message: err instanceof ApiError ? err.message : "Something went wrong.",
          });
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [activeOrgId]);

  if (!activeOrgId) {
    return (
      <div className="space-y-4">
        <PageHeader title="Team" />
        <Alert tone="info">
          Choose an organisation in the switcher above, or{" "}
          <Link href="/organisations/new" className="underline">
            create one
          </Link>
          .
        </Alert>
      </div>
    );
  }

  if (state.kind === "loading") return <Loading>Loading the team...</Loading>;
  if (state.kind === "error") return <Alert tone="error">{state.message}</Alert>;

  const { org } = state;
  const manage = canManage(org.role) && org.status === "active";

  return (
    <div className="space-y-6">
      <PageHeader title="Team" description={org.name} />
      {org.status === "archived" && (
        <Alert tone="info">This organisation is archived, so the team is view-only.</Alert>
      )}
      {org.role === "consultant" ? (
        <Alert tone="info">
          You have read-only consultant access to {org.name}. The team list is only visible to its
          members.
        </Alert>
      ) : (
        <>
          {manage && (
            <InviteCard
              org={org}
              onInvited={(invitation) =>
                setState({
                  ...state,
                  // Inviting the same email again replaces the old link.
                  invitations: [
                    invitation,
                    ...state.invitations.filter((i) => i.email !== invitation.email),
                  ],
                })
              }
            />
          )}
          {manage && state.invitations.length > 0 && (
            <InvitationsCard
              invitations={state.invitations}
              onCancelled={(id) =>
                setState({ ...state, invitations: state.invitations.filter((i) => i.id !== id) })
              }
            />
          )}
          <MembersCard
            org={org}
            manage={manage}
            members={state.members}
            onChanged={(member) =>
              setState({
                ...state,
                members: state.members.map((m) => (m.id === member.id ? member : m)),
              })
            }
            onRemoved={(id) =>
              setState({ ...state, members: state.members.filter((m) => m.id !== id) })
            }
          />
        </>
      )}
    </div>
  );
}

function InviteCard({
  org,
  onInvited,
}: {
  org: OrganisationOut;
  onInvited: (invitation: InvitationOut) => void;
}) {
  const { busy, error, run } = useSubmit();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<MembershipRole>("member");
  const [sentTo, setSentTo] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSentTo(null);
    const invitation = await run(() => sendInvitation(email, role));
    if (invitation) {
      onInvited(invitation);
      setSentTo(invitation.email);
      setEmail("");
    }
  }

  return (
    <Card>
      <CardTitle>Invite a team member</CardTitle>
      <p className="mt-1 text-sm text-neutral-600">
        We email them a link to join {org.name}. Inviting the same email again replaces the old
        link.
      </p>
      <form
        onSubmit={(e) => void handleSubmit(e)}
        className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end"
        noValidate
      >
        <div className="flex-1">
          <TextField
            label="Email"
            type="email"
            name="invite_email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="sm:w-48">
          <SelectField
            label="Role"
            name="invite_role"
            value={role}
            onChange={(e) => setRole(e.target.value as MembershipRole)}
          >
            {assignableRoles(org.role).map((r) => (
              <option key={r} value={r}>
                {roleLabel(r)}
              </option>
            ))}
          </SelectField>
        </div>
        <Button type="submit" busy={busy}>
          Send invitation
        </Button>
      </form>
      {error && (
        <div className="mt-3">
          <Alert tone="error">{error.message}</Alert>
        </div>
      )}
      {sentTo && (
        <div className="mt-3">
          <Alert tone="success">Invitation sent to {sentTo}.</Alert>
        </div>
      )}
    </Card>
  );
}

function InvitationsCard({
  invitations,
  onCancelled,
}: {
  invitations: InvitationOut[];
  onCancelled: (id: string) => void;
}) {
  const { busy, error, run } = useSubmit();
  const [busyId, setBusyId] = useState<string | null>(null);

  async function handleCancel(id: string) {
    setBusyId(id);
    const result = await run(() => cancelInvitation(id));
    setBusyId(null);
    if (result) onCancelled(id);
  }

  return (
    <Card>
      <CardTitle>Invitations waiting</CardTitle>
      {error && (
        <div className="mt-3">
          <Alert tone="error">{error.message}</Alert>
        </div>
      )}
      <ul className="mt-2 divide-y divide-neutral-200">
        {invitations.map((invitation) => (
          <li
            key={invitation.id}
            className="flex flex-wrap items-center gap-x-4 gap-y-2 py-3 text-sm"
          >
            <span className="font-medium text-neutral-900">{invitation.email}</span>
            <Badge>{roleLabel(invitation.role)}</Badge>
            {invitation.expired ? (
              <Badge tone="red">Expired</Badge>
            ) : (
              <span className="text-neutral-600">valid until {formatDate(invitation.expires_at)}</span>
            )}
            {invitation.invited_by_name && (
              <span className="text-neutral-500">invited by {invitation.invited_by_name}</span>
            )}
            <span className="ml-auto">
              <ConfirmButton
                label="Cancel"
                confirmLabel="Cancel invitation?"
                busy={busy && busyId === invitation.id}
                onConfirm={() => void handleCancel(invitation.id)}
              />
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function MembersCard({
  org,
  manage,
  members,
  onChanged,
  onRemoved,
}: {
  org: OrganisationOut;
  manage: boolean;
  members: MemberOut[];
  onChanged: (member: MemberOut) => void;
  onRemoved: (id: string) => void;
}) {
  const { busy, error, run } = useSubmit();
  const [busyId, setBusyId] = useState<string | null>(null);

  // Only an owner may change or remove an owner (the backend keeps the last owner anyway).
  function mayEdit(member: MemberOut): boolean {
    return manage && (member.role !== "owner" || org.role === "owner");
  }

  async function handleRoleChange(member: MemberOut, role: MembershipRole) {
    setBusyId(member.id);
    const changed = await run(() => changeMemberRole(member.id, role));
    setBusyId(null);
    if (changed) onChanged(changed);
  }

  async function handleRemove(member: MemberOut) {
    setBusyId(member.id);
    const result = await run(() => removeMember(member.id));
    setBusyId(null);
    if (result) onRemoved(member.id);
  }

  return (
    <Card>
      <CardTitle>Members</CardTitle>
      {error && (
        <div className="mt-3">
          <Alert tone="error">{error.message}</Alert>
        </div>
      )}
      <ul className="mt-2 divide-y divide-neutral-200">
        {members.map((member) => (
          <li
            key={member.id}
            className="flex flex-wrap items-center gap-x-4 gap-y-2 py-3 text-sm"
          >
            <span className="min-w-0">
              <span className="block font-medium text-neutral-900">{member.name}</span>
              <span className="block text-neutral-600">{member.email}</span>
            </span>
            <span className="text-neutral-500">joined {formatDate(member.joined_at)}</span>
            <span className="ml-auto flex items-center gap-3">
              {mayEdit(member) ? (
                <>
                  <SelectField
                    label={`Role of ${member.name}`}
                    labelHidden
                    value={member.role}
                    disabled={busy && busyId === member.id}
                    onChange={(e) =>
                      void handleRoleChange(member, e.target.value as MembershipRole)
                    }
                  >
                    {assignableRoles(org.role).map((r) => (
                      <option key={r} value={r}>
                        {roleLabel(r)}
                      </option>
                    ))}
                  </SelectField>
                  <ConfirmButton
                    label="Remove"
                    confirmLabel="Remove member?"
                    busy={busy && busyId === member.id}
                    onConfirm={() => void handleRemove(member)}
                  />
                </>
              ) : (
                <Badge>{roleLabel(member.role)}</Badge>
              )}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}
