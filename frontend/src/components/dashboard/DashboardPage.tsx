"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";

import { useMe } from "@/components/app/me-context";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Card, CardTitle, PageHeader } from "@/components/ui/Card";
import { Loading } from "@/components/ui/Loading";
import { ApiError } from "@/lib/api/client";
import { listGrants } from "@/lib/api/consultants";
import { assessmentHref, listAssessments } from "@/lib/api/readiness";
import { getOrganisation } from "@/lib/api/organisation";
import { listInvitations, listMembers } from "@/lib/api/team";
import type {
  AssessmentSummaryOut,
  ConsultantGrantOut,
  InvitationOut,
  MemberOut,
  OrganisationOut,
} from "@/lib/api/types";
import { formatDate } from "@/lib/format";
import { canManage, roleLabel, roleWithArticle } from "@/lib/roles";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | {
      kind: "ready";
      org: OrganisationOut;
      members: MemberOut[];
      invitations: InvitationOut[];
      grants: ConsultantGrantOut[];
      assessments: AssessmentSummaryOut[];
    };

const TEAM_PREVIEW = 5;

/** The signed-in home: who you are here, the organisation at a glance, and what to do next.
 * Every figure comes from the API; nothing is estimated. */
export function DashboardPage() {
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
        const consultant = org.role === "consultant";
        const manage = canManage(org.role) && org.status === "active";
        const [members, invitations, grants, assessments] = await Promise.all([
          consultant ? Promise.resolve([]) : listMembers(),
          manage ? listInvitations() : Promise.resolve([]),
          manage ? listGrants() : Promise.resolve([]),
          listAssessments(),
        ]);
        if (!cancelled) {
          setState({ kind: "ready", org, members, invitations, grants, assessments });
        }
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

  const firstName = me.name.trim().split(/\s+/)[0] || me.name;

  if (!activeOrgId) {
    return (
      <div className="space-y-6">
        <PageHeader
          title={`Welcome, ${firstName}`}
          description="Set up your organisation to start measuring how ready it is to innovate."
        />
        <Card>
          <CardTitle>Get started</CardTitle>
          <p className="mt-1 text-sm text-neutral-600">
            Create your organisation; you become its owner and can invite your team.
          </p>
          <div className="mt-4 flex flex-wrap gap-3">
            <ActionLink href="/organisations/new" primary>
              Create an organisation
            </ActionLink>
            {me.consultant_organisations.length > 0 && (
              <ActionLink href="/consultant-access">Organisations you consult for</ActionLink>
            )}
          </div>
        </Card>
      </div>
    );
  }

  if (state.kind === "loading") return <Loading>Loading your dashboard...</Loading>;
  if (state.kind === "error") return <Alert tone="error">{state.message}</Alert>;

  const { org } = state;

  if (org.role === "consultant") {
    const access = me.consultant_organisations.find((o) => o.organisation_id === org.id);
    return (
      <div className="space-y-6">
        <PageHeader title={`Welcome, ${firstName}`} description={org.name} />
        <Alert tone="info">
          You have read-only consultant access to {org.name}
          {access ? ` until ${formatDate(access.access_ends_at)}` : ""}.
        </Alert>
        <ReadinessCard latest={state.assessments[0]} manage={false} consultant />
        <Card>
          <CardTitle>Your consulting access</CardTitle>
          <p className="mt-1 text-sm text-neutral-600">
            See every organisation that has given you access, and accept new invitations.
          </p>
          <div className="mt-4">
            <ActionLink href="/consultant-access">My access</ActionLink>
          </div>
        </Card>
      </div>
    );
  }

  const manage = canManage(org.role) && org.status === "active";
  const waitingInvitations = state.invitations.filter((i) => !i.expired);
  const activeGrants = state.grants.filter((g) => g.status === "active");
  const openGrants = state.grants.filter((g) => g.status === "active" || g.status === "waiting");
  const profileComplete = Boolean(org.industry && org.country && org.size_band);

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Welcome back, ${firstName}`}
        description={`${org.name} · you are ${roleWithArticle(org.role)}`}
      />
      {org.status === "archived" && (
        <Alert tone="info">This organisation is archived, so it is view-only.</Alert>
      )}

      <section aria-label="At a glance" className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Team members" value={state.members.length} />
        {manage && <Stat label="Invitations waiting" value={waitingInvitations.length} />}
        {manage && (
          <Stat
            label="Consultant access"
            value={activeGrants.length}
            hint={
              openGrants.length > activeGrants.length
                ? `${openGrants.length - activeGrants.length} waiting to accept`
                : undefined
            }
          />
        )}
        <Stat label="Currency" value={org.currency} />
      </section>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {manage ? (
          <Card>
            <CardTitle>Getting started</CardTitle>
            <ol className="mt-3 space-y-3">
              <Step done label="Create your organisation" />
              <Step
                done={profileComplete}
                label="Complete the organisation profile"
                hint="Industry, country and company size."
                href="/organisation"
              />
              <Step
                done={state.members.length > 1}
                label="Invite your team"
                hint="Each person answers the readiness questions on their own."
                href="/team"
              />
              <Step
                done={openGrants.length > 0}
                label="Give your consultant access"
                hint="Optional. Read-only, until an end date you choose."
                href="/consultants"
              />
              <Step
                done={state.assessments.some((a) => a.status === "final")}
                label="Run the readiness assessment"
                hint="Your team answers 60 questions and agrees a score out of 300."
                href="/readiness"
              />
            </ol>
          </Card>
        ) : (
          <ReadinessCard latest={state.assessments[0]} manage={false} />
        )}

        <Card>
          <div className="flex items-baseline justify-between gap-4">
            <CardTitle>Your team</CardTitle>
            <Link href="/team" className="text-sm text-primary hover:underline">
              View all
            </Link>
          </div>
          <ul className="mt-2 divide-y divide-neutral-200">
            {state.members.slice(0, TEAM_PREVIEW).map((member) => (
              <li key={member.id} className="flex items-center justify-between gap-3 py-2.5">
                <span className="min-w-0 truncate text-sm text-neutral-900">
                  {member.name}
                  {member.user_id === me.id && <span className="text-neutral-500"> (you)</span>}
                </span>
                <Badge>{roleLabel(member.role)}</Badge>
              </li>
            ))}
          </ul>
          {state.members.length > TEAM_PREVIEW && (
            <p className="mt-2 text-xs text-neutral-500">
              and {state.members.length - TEAM_PREVIEW} more
            </p>
          )}
        </Card>
      </div>

      {manage && <ReadinessCard latest={state.assessments[0]} manage />}

      <Card>
        <CardTitle>Quick actions</CardTitle>
        <div className="mt-4 flex flex-wrap gap-3">
          {manage && (
            <ActionLink href="/team" primary>
              Invite a team member
            </ActionLink>
          )}
          {manage && <ActionLink href="/organisation">Organisation settings</ActionLink>}
          {manage && <ActionLink href="/consultants">Consultant access</ActionLink>}
          {!manage && <ActionLink href="/team">See the team</ActionLink>}
          <ActionLink href="/account">Your account</ActionLink>
        </div>
      </Card>
    </div>
  );
}

function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-medium tracking-wide text-neutral-500 uppercase">{label}</p>
      <p className="mt-1 font-serif text-2xl font-semibold text-neutral-900">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-neutral-500">{hint}</p>}
    </div>
  );
}

function Step({
  done,
  label,
  hint,
  href,
}: {
  done: boolean;
  label: string;
  hint?: string;
  href?: string;
}) {
  return (
    <li className="flex items-start gap-3">
      <span
        aria-hidden="true"
        className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs ${
          done ? "bg-accent text-white" : "border border-neutral-300 bg-white"
        }`}
      >
        {done ? "✓" : ""}
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-center gap-2 text-sm text-neutral-900">
          {href && !done ? (
            <Link href={href} className="font-medium text-primary hover:underline">
              {label}
            </Link>
          ) : (
            <span className={done ? "text-neutral-500 line-through" : "font-medium"}>{label}</span>
          )}
          <span className="sr-only">{done ? "(done)" : "(to do)"}</span>
        </span>
        {hint && !done && <span className="mt-0.5 block text-xs text-neutral-500">{hint}</span>}
      </span>
    </li>
  );
}

/** The latest readiness assessment's real state, and the one link that moves it forward. */
function ReadinessCard({
  latest,
  manage,
  consultant = false,
}: {
  latest: AssessmentSummaryOut | undefined;
  manage: boolean;
  consultant?: boolean;
}) {
  let body: ReactNode;
  let action: ReactNode = null;
  if (!latest) {
    body = consultant
      ? "The team's readiness result out of 300, with its band and the 12 dimension scores, will appear here once it is final."
      : "Your team answers 60 questions across the 12 Dimensions of Innovation and agrees a score out of 300.";
    if (manage) {
      action = (
        <ActionLink href="/readiness" primary>
          Start a readiness assessment
        </ActionLink>
      );
    } else if (!consultant) {
      body = `${body} An owner or admin starts it.`;
    }
  } else if (latest.status === "final") {
    body = (
      <>
        <span className="block font-serif text-3xl font-semibold text-neutral-900">
          {latest.total}
          <span className="ml-1 text-lg text-neutral-500">/ 300</span>
        </span>
        <span className="mt-1 block font-medium text-primary">{latest.band_name}</span>
        <span className="mt-1 block">
          Final on {formatDate(latest.finalised_at ?? latest.created_at)}.
        </span>
      </>
    );
    action = (
      <ActionLink href={assessmentHref(latest, manage)} primary>
        See the result
      </ActionLink>
    );
  } else if (latest.status === "consensus") {
    body = manage
      ? `Answers are closed with ${latest.submitted_count} submitted. Agree the team's answers to finish.`
      : "The team's answers are being agreed. The result appears here once it is final.";
    if (manage) {
      action = (
        <ActionLink href={assessmentHref(latest, manage)} primary>
          Agree the answers
        </ActionLink>
      );
    }
  } else {
    const mine =
      latest.my_status === "submitted"
        ? "You have submitted your answers."
        : latest.my_status === "in_progress"
          ? "Your answers are in progress."
          : latest.my_status === "not_started"
            ? "You have not started yet."
            : "";
    body = `Collecting answers: ${latest.submitted_count} submitted so far. ${mine}`.trim();
    if (latest.my_status && latest.my_status !== "submitted") {
      action = (
        <ActionLink href={assessmentHref(latest, manage)} primary>
          Answer the questions
        </ActionLink>
      );
    } else if (manage) {
      action = <ActionLink href={assessmentHref(latest, manage)}>See the team&apos;s progress</ActionLink>;
    }
  }

  return (
    <Card>
      <CardTitle>Readiness assessment</CardTitle>
      <div className="mt-2 text-sm text-neutral-600">{body}</div>
      {action && <div className="mt-4">{action}</div>}
    </Card>
  );
}

function ActionLink({
  href,
  primary = false,
  children,
}: {
  href: string;
  primary?: boolean;
  children: ReactNode;
}) {
  return (
    <Link
      href={href}
      className={`inline-flex items-center justify-center rounded-full px-4 py-2 text-sm font-medium transition-colors ${
        primary
          ? "bg-primary text-white hover:bg-primary-strong"
          : "border border-neutral-300 bg-white text-neutral-900 hover:bg-neutral-50"
      }`}
    >
      {children}
    </Link>
  );
}
