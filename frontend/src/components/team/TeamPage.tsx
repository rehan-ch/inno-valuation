
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Building2,
  CalendarDays,
  Clock3,
  Compass,
  Crown,
  Mail,
  MailPlus,
  Send,
  Shield,
  ShieldCheck,
  Sparkles,
  UserRoundCheck,
  UserRoundPlus,
  UsersRound,
} from "lucide-react";

import { MemberRoleSelector } from "./MemberRoleSelector";
import { useMe } from "@/components/app/me-context";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
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
import { emailError, useSubmit } from "@/lib/forms";
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

const surface =
  "rounded-[24px] border border-[#DDE5F0] bg-white shadow-[0_10px_35px_-24px_rgba(8,23,43,0.35)]";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);

  const first = parts[0] ?? "";
  const last = parts[parts.length - 1] ?? "";

  if (!first) return "U";

  if (parts.length === 1) {
    return first.slice(0, 2).toUpperCase();
  }

  return `${first.charAt(0)}${last.charAt(0)}`.toUpperCase();
}

function Avatar({
  name,
  gold = false,
  size = "normal",
}: {
  name: string;
  gold?: boolean;
  size?: "normal" | "large";
}) {
  return (
    <span
      aria-hidden="true"
      className={`inline-flex shrink-0 items-center justify-center
        rounded-2xl border font-sans font-bold tracking-tight
        ${size === "large"
          ? "h-14 w-14 text-lg sm:h-16 sm:w-16"
          : "h-12 w-12 text-sm"
        }
        ${gold
          ? "border-[#EBD4AA] bg-[#FBF3E4] text-[#A27229]"
          : "border-[#D6E5F1] bg-[#EBF3FA] text-[#183B60]"
        }`}
    >
      {initials(name)}
    </span>
  );
}

function RolePill({ role }: { role: MembershipRole }) {
  const owner = role === "owner";
  const admin = role === "admin";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full
        border px-3 py-1.5 font-sans text-[11px] font-semibold
        ${owner
          ? "border-[#E9D4AD] bg-[#FBF3E5] text-[#96671F]"
          : admin
            ? "border-[#C9DDF1] bg-[#EDF5FD] text-[#245B87]"
            : "border-[#E1E7EF] bg-[#F4F7FB] text-[#52647D]"
        }`}
    >
      {owner ? (
        <Crown size={12} aria-hidden="true" />
      ) : admin ? (
        <ShieldCheck size={12} aria-hidden="true" />
      ) : (
        <UsersRound size={12} aria-hidden="true" />
      )}
      {roleLabel(role)}
    </span>
  );
}

function SectionHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
      <div>
        <div className="mb-2 flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-[#DDB468]" />
          <span className="font-sans text-[10px] font-bold uppercase tracking-[0.2em] text-[#A37535]">
            {eyebrow}
          </span>
        </div>
        <h2 className="font-sans text-[23px] font-bold tracking-[-0.045em] text-[#0A1A30] sm:text-[27px]">
          {title}
        </h2>
        <p className="mt-1 font-sans text-sm leading-6 text-[#70819A]">
          {description}
        </p>
      </div>
      {action}
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  description,
}: {
  icon: ReactNode;
  label: string;
  value: number;
  description: string;
}) {
  return (
    <div
      className={`${surface} group relative overflow-hidden p-5
        transition-all duration-300 hover:-translate-y-1
        hover:border-[#E5CB9D] hover:shadow-[0_18px_45px_-22px_rgba(8,23,43,0.22)]
        sm:p-6`}
    >
      <span
        aria-hidden="true"
        className="pointer-events-none absolute -right-7 -top-8
          h-28 w-28 rounded-full bg-[#FAF4E9] opacity-60
          blur-2xl"
      />
      <div className="relative flex items-start justify-between gap-3">
        <span
          className="flex h-11 w-11 items-center justify-center rounded-2xl
            border border-[#EEDDBE] bg-[#FCF6EC] text-[#AD7A31]
            transition-transform duration-300 group-hover:scale-110"
        >
          {icon}
        </span>
        <ArrowUpRight
          size={17}
          className="text-[#B7C4D5]"
          aria-hidden="true"
        />
      </div>
      <div className="relative mt-5">
        <p className="font-sans text-[11px] font-semibold uppercase tracking-[0.12em] text-[#74859B]">
          {label}
        </p>
        <p className="mt-1 font-sans text-[35px] font-bold leading-none tracking-[-0.06em] text-[#0A1A30]">
          {value}
        </p>
        <p className="mt-2 font-sans text-xs text-[#8797AC]">
          {description}
        </p>
      </div>
    </div>
  );
}

function TeamHero({
  org,
  members,
  manage,
}: {
  org: OrganisationOut;
  members: MemberOut[];
  invitations: InvitationOut[];
  manage: boolean;
}) {
  return (
    <section
      className="relative isolate overflow-hidden rounded-[28px]
        border border-[#20334F] bg-[#08172B] px-6 py-8
        shadow-[0_22px_55px_-30px_rgba(5,18,37,0.45)]
        sm:px-9 sm:py-10 lg:px-11"
    >
      <div
        aria-hidden="true"
        className="absolute left-10 top-0 h-[3px] w-28 rounded-full bg-[#E6B968]"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-24 -top-32
          h-[440px] w-[440px] rounded-full border border-[#DDB468]/10"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-12 -top-20
          h-[350px] w-[350px] rounded-full border border-[#DDB468]/10"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-52 right-20
          h-[360px] w-[360px] rounded-full bg-[#1D385A]/30 blur-3xl"
      />

      <div className="relative z-10 grid items-center gap-8 lg:grid-cols-[minmax(0,1fr)_270px]">
        <div>
          <div className="mb-5 flex items-center gap-2.5">
            <Sparkles
              size={14}
              className="text-[#E6BA70]"
              aria-hidden="true"
            />
            <span className="font-sans text-[10px] font-bold uppercase tracking-[0.21em] text-[#E6BA70]">
              People & collaboration
            </span>
          </div>

          <h1 className="font-sans text-[34px] font-bold leading-[1.08] tracking-[-0.055em] text-white sm:text-[43px] lg:text-[49px]">
            Great ideas grow
            <span className="block text-[#E6BA70]">together.</span>
          </h1>

          <p className="mt-4 max-w-xl font-sans text-sm leading-7 text-[#A8B8CE] sm:text-[15px]">
            Bring your people together, manage permissions, and
            build a stronger innovation team in one connected
            workspace.
          </p>

          <div className="mt-6 flex flex-wrap items-center gap-2.5">
            <span
              className="inline-flex max-w-full items-center gap-2 rounded-xl
                border border-white/15 bg-white/[0.07] px-3 py-2
                font-sans text-xs font-medium text-[#DAE3F1]"
            >
              <Building2
                size={14}
                className="shrink-0 text-[#E6BA70]"
              />
              <span className="truncate">{org.name}</span>
            </span>
            <span
              className="inline-flex items-center gap-2 rounded-xl border
                border-white/15 bg-white/[0.07] px-3 py-2
                font-sans text-xs text-[#DAE3F1]"
            >
              <ShieldCheck size={14} className="text-[#E6BA70]" />
              {roleLabel(org.role)} access
            </span>
          </div>

          {manage && (
            <a
              href="#invite-team"
              className="mt-7 inline-flex min-h-11 items-center
                justify-center gap-2.5 rounded-xl bg-[#E2B96D]
                px-5 py-3 font-sans text-sm font-bold
                text-[#09182C] shadow-[0_8px_25px_-12px_#E2B96D]
                transition-all duration-300
                hover:-translate-y-0.5 hover:bg-[#F0CB86]
                focus-visible:outline-2 focus-visible:outline-offset-4
                focus-visible:outline-[#E2B96D]"
            >
              <UserRoundPlus size={17} />
              Invite a member
              <ArrowUpRight size={16} />
            </a>
          )}
        </div>

        <div
          aria-hidden="true"
          className="relative mx-auto hidden h-[245px] w-[245px]
            items-center justify-center lg:flex"
        >
          <div className="absolute inset-0 rounded-full border border-[#E6BA70]/20" />
          <div className="absolute inset-5 rounded-full border border-[#E6BA70]/15" />
          <div className="absolute inset-12 rounded-full border border-[#E6BA70]/20 bg-[#10243F]" />

          <div className="absolute left-8 top-10 flex h-12 w-12 items-center justify-center rounded-2xl border border-[#E6BA70]/45 bg-[#182D49] text-[#E6BA70] shadow-xl">
            <Compass size={23} strokeWidth={1.5} />
          </div>
          <div className="absolute bottom-8 left-7 flex h-12 w-12 items-center justify-center rounded-2xl border border-[#E6BA70]/35 bg-[#162B47] text-[#E6BA70] shadow-xl">
            <ShieldCheck size={22} />
          </div>
          <div className="absolute right-4 top-20 flex h-12 w-12 items-center justify-center rounded-2xl border border-[#E6BA70]/35 bg-[#162B47] text-[#E6BA70] shadow-xl">
            <Sparkles size={22} />
          </div>
          <div className="relative flex h-24 w-24 items-center justify-center rounded-[28px] border border-[#E6BA70]/45 bg-[#1B3554] shadow-[0_0_45px_rgba(230,186,112,0.12)]">
            <UsersRound
              size={43}
              strokeWidth={1.35}
              className="text-[#E6BA70]"
            />
          </div>
          <span className="absolute bottom-1 right-5 rounded-full border border-[#E6BA70]/25 bg-[#10243D] px-3 py-1.5 font-sans text-[10px] font-semibold text-[#E6BA70]">
            {members.length} team members
          </span>
        </div>
      </div>
    </section>
  );
}

export function TeamPage() {
  const { me } = useMe();
  const activeOrgId = me.active_organisation_id;
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    if (!activeOrgId) return;

    let cancelled = false;

    async function load() {
      // Drop the previous organisation's rows at once: the team endpoints act on the
      // session's active organisation, so stale controls would act on the new one.
      setState({ kind: "loading" });
      try {
        const org = await getOrganisation();
        const members =
          org.role === "consultant" ? [] : await listMembers();
        const manage =
          canManage(org.role) && org.status === "active";
        const invitations = manage ? await listInvitations() : [];

        if (!cancelled) {
          setState({
            kind: "ready",
            org,
            members,
            invitations,
          });
        }
      } catch (err) {
        if (!cancelled) {
          setState({
            kind: "error",
            message:
              err instanceof ApiError
                ? err.message
                : "Something went wrong.",
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
      <div className="mx-auto max-w-3xl py-12">
        <div className={`${surface} p-8 text-center sm:p-12`}>
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-[#FBF2E3] text-[#AD7A31]">
            <Building2 size={28} />
          </div>
          <h1 className="mt-5 font-sans text-3xl font-bold tracking-tight text-[#08172B]">
            Your team workspace
          </h1>
          <p className="mx-auto mt-3 max-w-md font-sans text-sm leading-7 text-[#718198]">
            Select an organisation to see your people and
            collaboration tools.
          </p>
          <div className="mt-6">
            <Alert tone="info">
              Choose an organisation in the switcher above, or{" "}
              <Link
                href="/organisations/new"
                className="font-semibold underline"
              >
                create one
              </Link>
              .
            </Alert>
          </div>
        </div>
      </div>
    );
  }

  if (state.kind === "loading") {
    return <Loading>Loading the team...</Loading>;
  }

  if (state.kind === "error") {
    return <Alert tone="error">{state.message}</Alert>;
  }

  const { org, members, invitations } = state;
  const manage =
    canManage(org.role) && org.status === "active";
  const pending = invitations.filter((i) => !i.expired).length;

  return (
    <div className="iv-team-page mx-auto max-w-[1320px] space-y-9 pb-16 font-sans">
      <TeamHero
        org={org}
        members={members}
        invitations={invitations}
        manage={manage}
      />

      {org.status === "archived" && (
        <Alert tone="info">
          This organisation is archived, so the team is view-only.
        </Alert>
      )}

      {org.role === "consultant" ? (
        <div className={`${surface} p-7 sm:p-10`}>
          <div className="mb-5 inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-[#EDF4FB] text-[#285A85]">
            <Shield size={26} />
          </div>
          <h2 className="font-sans text-2xl font-bold text-[#08172B]">
            Your consultant workspace
          </h2>
          <p className="mt-3 max-w-xl font-sans text-sm leading-7 text-[#718198]">
            You have read-only consultant access to {org.name}.
            The team list is only visible to its members.
          </p>
          <Link
            href="/consultant-access"
            className="mt-6 inline-flex items-center gap-2
              font-sans text-sm font-semibold text-[#A37535]
              hover:text-[#08172B]"
          >
            View my access <ArrowRight size={16} />
          </Link>
        </div>
      ) : (
        <>
          <section aria-label="Team overview">
            <SectionHeading
              eyebrow="Workspace overview"
              title="Your people, at a glance."
              description="A clear overview of your organisation's collaboration."
            />
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <StatCard
                icon={<UsersRound size={21} strokeWidth={1.7} />}
                label="Team members"
                value={members.length}
                description="People in your workspace"
              />
              <StatCard
                icon={<Mail size={21} strokeWidth={1.7} />}
                label="Pending invitations"
                value={pending}
                description="Awaiting acceptance"
              />
              <StatCard
                icon={<UserRoundCheck size={21} strokeWidth={1.7} />}
                label="Owners and admins"
                value={members.filter((m) => canManage(m.role)).length}
                description="Can manage the team"
              />
            </div>
          </section>

          {manage && (
            <section id="invite-team" className="scroll-mt-28">
              <SectionHeading
                eyebrow="Grow your workspace"
                title="Bring great minds together."
                description="Invite colleagues into your innovation journey."
              />
              <InviteCard
                org={org}
                onInvited={(invitation) =>
                  setState((prev) =>
                    prev.kind === "ready"
                      ? {
                        ...prev,
                        invitations: [
                          invitation,
                          ...prev.invitations.filter(
                            (i) => i.email !== invitation.email,
                          ),
                        ],
                      }
                      : prev,
                  )
                }
              />
            </section>
          )}

          <section>
            <SectionHeading
              eyebrow="People directory"
              title="Your team."
              description="Everyone contributing to your organisation."
              action={
                <span className="rounded-full border border-[#E4D3B6] bg-[#FBF4E8] px-3.5 py-2 text-xs font-semibold text-[#9A6B29]">
                  {members.length} members
                </span>
              }
            />
            <MembersCard
              org={org}
              manage={manage}
              members={members}
              onChanged={(member) =>
                setState((prev) =>
                  prev.kind === "ready"
                    ? {
                      ...prev,
                      members: prev.members.map((m) =>
                        m.id === member.id ? member : m,
                      ),
                    }
                    : prev,
                )
              }
              onRemoved={(id) =>
                setState((prev) =>
                  prev.kind === "ready"
                    ? {
                      ...prev,
                      members: prev.members.filter(
                        (m) => m.id !== id,
                      ),
                    }
                    : prev,
                )
              }
            />
          </section>

          {manage && invitations.length > 0 && (
            <section>
              <SectionHeading
                eyebrow="Invitation centre"
                title="Invitations waiting."
                description="Manage invitations that have not yet been accepted."
              />
              <InvitationsCard
                invitations={invitations}
                onCancelled={(id) =>
                  setState((prev) =>
                    prev.kind === "ready"
                      ? {
                        ...prev,
                        invitations: prev.invitations.filter(
                          (i) => i.id !== id,
                        ),
                      }
                      : prev,
                  )
                }
              />
            </section>
          )}

          <div
            className="flex flex-wrap items-center justify-between gap-4
              rounded-2xl border border-[#DEE6F0] bg-white/65
              px-5 py-4 sm:px-6"
          >
            <div className="flex items-center gap-3">
              <ShieldCheck
                size={19}
                className="text-[#A97935]"
                aria-hidden="true"
              />
              <p className="font-sans text-xs leading-6 text-[#728198]">
                Team permissions are managed securely through
                your organisation.
              </p>
            </div>
            <Link
              href="/readiness"
              className="inline-flex items-center gap-2 font-sans
                text-xs font-bold text-[#183B60]
                transition-colors hover:text-[#A97935]"
            >
              Go to Readiness
              <ArrowUpRight size={15} />
            </Link>
          </div>
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
  const [emailFieldError, setEmailFieldError] = useState<
    string | undefined
  >(undefined);
  const [role, setRole] = useState<MembershipRole>("member");
  const [sentTo, setSentTo] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSentTo(null);

    const invalid = emailError(email);

    if (invalid) {
      setEmailFieldError(invalid);
      return;
    }

    const invitation = await run(() => sendInvitation(email, role));

    if (invitation) {
      onInvited(invitation);
      setSentTo(invitation.email);
      setEmail("");
    }
  }

  return (
    <div className={`${surface} overflow-hidden`}>
      <div className="grid lg:grid-cols-[minmax(0,1fr)_255px]">
        <div className="p-5 sm:p-8">
          <div className="mb-5 flex items-start gap-4">
            <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-[#EEDDBE] bg-[#FBF4E8] text-[#A97935]">
              <MailPlus size={22} />
            </span>
            <div>
              <h3 className="font-sans text-lg font-bold tracking-tight text-[#08172B]">
                Invite a team member
              </h3>
              <p className="mt-1 max-w-lg font-sans text-sm leading-6 text-[#74849B]">
                We email them a link to join {org.name}.
                Inviting the same email again replaces the old link.
              </p>
            </div>
          </div>

          <form
            onSubmit={(event) => void handleSubmit(event)}
            className="space-y-4"
            noValidate
          >
            <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_190px]">
              <div className="min-w-0">
                <TextField
                  label="Email"
                  type="email"
                  name="invite_email"
                  required
                  error={emailFieldError}
                  value={email}
                  onChange={(event) => {
                    setEmail(event.target.value);
                    setEmailFieldError(undefined);
                  }}
                />
              </div>
              <div className="min-w-0">
                <SelectField
                  label="Role"
                  name="invite_role"
                  value={role}
                  onChange={(event) =>
                    setRole(
                      event.target.value as MembershipRole,
                    )
                  }
                >
                  {assignableRoles(org.role).map((r) => (
                    <option key={r} value={r}>
                      {roleLabel(r)}
                    </option>
                  ))}
                </SelectField>
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-4 pt-1">
              <p className="flex items-center gap-2 font-sans text-xs text-[#8A99AC]">
                <ShieldCheck
                  size={15}
                  className="text-[#B58A48]"
                />
                Secure email invitation
              </p>
              <div className="[&_button]:min-h-11 [&_button]:rounded-xl [&_button]:bg-[#DDB468] [&_button]:px-6 [&_button]:font-sans [&_button]:font-bold [&_button]:text-[#08172B] [&_button]:transition-all [&_button]:duration-300 hover:[&_button]:bg-[#ECC784]">
                <Button type="submit" busy={busy}>
                  <Send size={15} className="mr-2 inline" />
                  Send invitation
                </Button>
              </div>
            </div>
          </form>

          {error && (
            <div className="mt-4">
              <Alert tone="error">{error.message}</Alert>
            </div>
          )}

          {sentTo && (
            <div className="mt-4">
              <Alert tone="success">
                Invitation sent to {sentTo}.
              </Alert>
            </div>
          )}
        </div>

        <aside className="relative hidden overflow-hidden border-l border-[#E6EAF0] bg-[#F8F5EE] p-7 lg:flex lg:flex-col lg:justify-center">
          <div
            aria-hidden="true"
            className="absolute -right-16 -top-16 h-44 w-44 rounded-full border border-[#E1CBA6]/45"
          />
          <div className="relative mb-6 flex items-center">
            <span className="flex h-14 w-14 items-center justify-center rounded-2xl border-4 border-[#F8F5EE] bg-[#E7CB98] text-[#6B4A1D]">
              <UsersRound size={23} />
            </span>
            <span className="-ml-2 flex h-14 w-14 items-center justify-center rounded-2xl border-4 border-[#F8F5EE] bg-[#D4E4F1] text-[#214D72]">
              <UserRoundPlus size={23} />
            </span>
            <span className="-ml-2 flex h-14 w-14 items-center justify-center rounded-2xl border-4 border-[#F8F5EE] bg-[#102944] text-[#E7C187]">
              <Sparkles size={23} />
            </span>
          </div>
          <p className="relative font-sans text-base font-bold leading-snug text-[#142A43]">
            Better collaboration starts with the right people.
          </p>
          <p className="relative mt-3 font-sans text-xs leading-6 text-[#7B8899]">
            Invite your colleagues and explore your innovation
            potential together.
          </p>
        </aside>
      </div>
    </div>
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

  function mayEdit(member: MemberOut): boolean {
    return (
      manage &&
      (member.role !== "owner" || org.role === "owner")
    );
  }

  async function handleRoleChange(
    member: MemberOut,
    role: MembershipRole,
  ) {
    setBusyId(member.id);
    const changed = await run(() =>
      changeMemberRole(member.id, role),
    );
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
    <section className={`${surface} relative overflow-visible`}>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#E9EDF3] px-5 py-5 sm:px-7">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#EFF4FA] text-[#264B72]">
            <UsersRound size={19} />
          </span>
          <div>
            <h3 className="font-sans text-base font-bold text-[#0C2139]">
              Members
            </h3>
            <p className="font-sans text-xs text-[#8695A9]">
              Organisation directory
            </p>
          </div>
        </div>
        <span className="inline-flex items-center gap-2 rounded-full bg-[#EDF6F2] px-3 py-1.5 font-sans text-[11px] font-semibold text-[#28795C]">
          <span className="h-1.5 w-1.5 rounded-full bg-[#32A77A]" />
          {members.length} joined
        </span>
      </div>

      {error && (
        <div className="px-5 pt-5 sm:px-7">
          <Alert tone="error">{error.message}</Alert>
        </div>
      )}

      {members.length === 0 ? (
        <div className="px-6 py-14 text-center">
          <UsersRound
            size={31}
            className="mx-auto text-[#B4C1D0]"
          />
          <p className="mt-4 font-sans text-sm font-semibold text-[#0C2139]">
            No members to display
          </p>
        </div>
      ) : (
        <ul className="divide-y divide-[#EDF0F5]">
          {members.map((member) => (
            <li
              key={member.id}
              className="iv-team-member-row group flex flex-col gap-4 px-5 py-5
              transition-colors duration-200
              hover:bg-[#FAFBFD]
              sm:px-7 lg:flex-row lg:items-center lg:justify-between"
            >
              <div className="flex min-w-0 items-start gap-3.5 sm:items-center">
                <Avatar
                  name={member.name}
                  gold={member.role === "owner"}
                />
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="break-words font-sans text-sm font-bold text-[#0D223B]">
                      {member.name}
                    </p>
                    {member.role === "owner" && (
                      <Crown
                        size={14}
                        className="text-[#C2954A]"
                        aria-label="Owner"
                      />
                    )}
                  </div>
                  <p className="mt-1 break-all font-sans text-xs text-[#7B8BA1]">
                    {member.email}
                  </p>
                  <p className="mt-2 inline-flex items-center gap-1.5 font-sans text-[11px] text-[#9AA7B7]">
                    <CalendarDays size={12} />
                    joined {formatDate(member.joined_at)}
                  </p>
                </div>
              </div>

              <div className="iv-team-member-actions lg:ml-auto">
                {mayEdit(member) ? (
                  <>
                    <div className="iv-role-selector">
                      <MemberRoleSelector
                        name={member.name}
                        value={member.role}
                        options={assignableRoles(org.role)}
                        disabled={busy}
                        onChange={(role) =>
                          void handleRoleChange(member, role)
                        }
                      />
                    </div>

                    <div className="iv-remove-button [&_button]:min-h-11 [&_button]:rounded-xl [&_button]:px-4 [&_button]:font-sans [&_button]:text-xs">
                      <ConfirmButton
                        label="Remove"
                        confirmLabel={`Remove ${roleLabel(member.role).toLowerCase()}?`}
                        busy={busy && busyId === member.id}
                        disabled={busy && busyId !== member.id}
                        onConfirm={() =>
                          void handleRemove(member)
                        }
                      />
                    </div>
                  </>
                ) : (
                  <RolePill role={member.role} />
                )}
              </div>


            </li>
          ))}
        </ul>
      )}
    </section>
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
    <section className={`${surface} overflow-hidden`}>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#E9EDF3] px-5 py-5 sm:px-7">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#FBF3E6] text-[#A97935]">
            <Mail size={19} />
          </span>
          <div>
            <h3 className="font-sans text-base font-bold text-[#0C2139]">
              Invitations waiting
            </h3>
            <p className="font-sans text-xs text-[#8695A9]">
              Track and manage invitations
            </p>
          </div>
        </div>
        <span className="rounded-full bg-[#FBF3E6] px-3 py-1.5 font-sans text-xs font-semibold text-[#A37635]">
          {invitations.length} total
        </span>
      </div>

      {error && (
        <div className="px-5 pt-5 sm:px-7">
          <Alert tone="error">{error.message}</Alert>
        </div>
      )}

      <ul className="divide-y divide-[#EDF0F5]">
        {invitations.map((invitation) => (
          <li
            key={invitation.id}
            className="flex flex-col gap-4 px-5 py-5
              transition-colors hover:bg-[#FAFBFD]
              sm:px-7 lg:flex-row lg:items-center
              lg:justify-between"
          >
            <div className="flex min-w-0 items-start gap-3.5">
              <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-[#EEDDBE] bg-[#FCF6EC] text-[#AD7A31]">
                <Mail size={19} />
              </span>
              <div className="min-w-0">
                <p className="break-all font-sans text-sm font-bold text-[#0C2139]">
                  {invitation.email}
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <RolePill role={invitation.role} />
                  {invitation.expired ? (
                    <span className="rounded-full bg-[#FDECEC] px-2.5 py-1 font-sans text-[11px] font-semibold text-[#B34848]">
                      Expired
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-[#FFF5E4] px-2.5 py-1 font-sans text-[11px] font-semibold text-[#A77935]">
                      <Clock3 size={12} />
                      Awaiting acceptance
                    </span>
                  )}
                </div>
                <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 font-sans text-[11px] text-[#8998AB]">
                  {!invitation.expired && (
                    <span>
                      valid until {formatDate(invitation.expires_at)}
                    </span>
                  )}
                  {invitation.invited_by_name && (
                    <span>
                      invited by {invitation.invited_by_name}
                    </span>
                  )}
                </div>
              </div>
            </div>

            <div className="pl-[62px] lg:pl-0 [&_button]:rounded-xl [&_button]:font-sans [&_button]:text-xs">
              <ConfirmButton
                label="Cancel"
                confirmLabel="Cancel invitation?"
                busy={busy && busyId === invitation.id}
                disabled={busy && busyId !== invitation.id}
                onConfirm={() =>
                  void handleCancel(invitation.id)
                }
              />
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
