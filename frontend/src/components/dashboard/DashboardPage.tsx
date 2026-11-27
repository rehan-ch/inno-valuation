
"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  BadgeCheck,
  Building2,
  Check,
  CheckCircle2,
  ChevronRight,
  Circle,
  ClipboardCheck,
  Compass,
  FileCheck2,
  Mail,
  Settings2,
  ShieldCheck,
  Sparkles,
  Target,
  UsersRound,
  Wallet,
} from "lucide-react";

import { useMe } from "@/components/app/me-context";
import { Alert } from "@/components/ui/Alert";
import { Loading } from "@/components/ui/Loading";
import { ApiError } from "@/lib/api/client";
import { listGrants } from "@/lib/api/consultants";
import { listIdeas } from "@/lib/api/ideas";
import { getDashboard } from "@/lib/api/insights";
import {
  Card,
  CardHeader,
  Eyebrow,
} from "@/components/ui/Card";
import { ScoresPanel } from "./ScoresPanel";
import { assessmentHref, listAssessments } from "@/lib/api/readiness";
import { getOrganisation } from "@/lib/api/organisation";
import { listInvitations, listMembers } from "@/lib/api/team";
import type {
  AssessmentSummaryOut,
  ConsultantGrantOut,
  DashboardOut,
  IdeaSummaryOut,
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
    ideas: IdeaSummaryOut[];
    dashboard: DashboardOut;
  };

type IconComponent = typeof Compass;

const TEAM_PREVIEW = 5;

function ActionLink({
  href,
  children,
  primary = false,
}: {
  href: string;
  children: ReactNode;
  primary?: boolean;
}) {
  return (
    <Link
      href={href}
      className={`iv-action ${primary ? "iv-action-primary" : "iv-action-secondary"
        }`}
    >
      <span>{children}</span>
      <ArrowRight size={16} strokeWidth={1.9} aria-hidden="true" />
    </Link>
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
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="iv-section-heading">
      <div>
        <p className="iv-eyebrow">{eyebrow}</p>
        <h2>{title}</h2>
        {description && <p className="iv-section-description">{description}</p>}
      </div>
      {action}
    </div>
  );
}

function MetricCard({
  icon: Icon,
  label,
  value,
  hint,
  href,
}: {
  icon: IconComponent;
  label: string;
  value: ReactNode;
  hint: string;
  href?: string;
}) {
  const content = (
    <>
      <div className="iv-metric-top">
        <span className="iv-metric-icon">
          <Icon size={19} strokeWidth={1.8} aria-hidden="true" />
        </span>
        {href && <ArrowUpRight size={17} className="iv-metric-arrow" />}
      </div>
      <div>
        <p className="iv-metric-label">{label}</p>
        <p className="iv-metric-value">{value}</p>
        <p className="iv-metric-hint">{hint}</p>
      </div>
    </>
  );

  return href ? (
    <Link href={href} className="iv-metric-card iv-metric-clickable">
      {content}
    </Link>
  ) : (
    <div className="iv-metric-card">{content}</div>
  );
}

function StepItem({
  label,
  hint,
  done,
  href,
}: {
  label: string;
  hint: string;
  done: boolean;
  href?: string;
}) {
  return (
    <li className={`iv-step ${done ? "iv-step-done" : ""}`}>
      <div className="iv-step-indicator" aria-hidden="true">
        {done ? <Check size={14} strokeWidth={2.5} /> : <Circle size={15} />}
      </div>
      <div className="iv-step-copy">
        <p className="iv-step-title">
          {href && !done ? (
            <Link href={href}>{label}</Link>
          ) : (
            <span>{label}</span>
          )}
          <span className="sr-only">{done ? "(done)" : "(to do)"}</span>
        </p>
        {!done && <p className="iv-step-hint">{hint}</p>}
      </div>
      {href && !done && (
        <Link
          href={href}
          className="iv-step-go"
          aria-label={`Go to ${label}`}
        >
          <ChevronRight size={17} aria-hidden="true" />
        </Link>
      )}
    </li>
  );
}

function SetupCard({
  org,
  members,
  grants,
  assessments,
  ideas,
  aiEnabled,
}: {
  org: OrganisationOut;
  members: MemberOut[];
  grants: ConsultantGrantOut[];
  assessments: AssessmentSummaryOut[];
  ideas: IdeaSummaryOut[];
  aiEnabled: boolean;
}) {
  const steps = [
    {
      label: "Create your organisation",
      hint: "Set up your innovation workspace.",
      done: true,
    },
    {
      label: "Complete organisation profile",
      hint: "Add your industry, country, and company size.",
      done: Boolean(org.industry && org.country && org.size_band),
      href: "/organisation",
    },
    {
      label: "Invite your team",
      hint: "Bring colleagues together for collaborative assessments.",
      done: members.length > 1,
      href: "/team",
    },
    {
      label: "Give consultant access",
      hint: "Optional read-only access with an expiry date.",
      done: grants.some(
        (g) => g.status === "active" || g.status === "waiting",
      ),
      href: "/consultants",
    },
    {
      label: "Run the readiness assessment",
      hint: "Understand your organisation's innovation readiness.",
      done: assessments.some((a) => a.status === "final"),
      href: "/readiness",
    },
    ...(aiEnabled
      ? [
        {
          label: "Score your first idea",
          hint: "Assess your idea and discover its Innovation IQ.",
          done: ideas.some((idea) => idea.status === "assessed"),
          href: "/ideas",
        },
      ]
      : []),
  ];

  const completed = steps.filter((step) => step.done).length;
  const progress = (completed / steps.length) * 100;

  return (
    <section className="iv-panel iv-setup-panel">
      <div className="iv-panel-top">
        <div className="iv-panel-icon">
          <Target size={19} />
        </div>
        <span className="iv-panel-kicker">WORKSPACE SETUP</span>
      </div>

      <div className="iv-panel-title-row">
        <div>
          <h3>Getting started</h3>
          <p>Build the foundations for smarter innovation decisions.</p>
        </div>
        <span className="iv-progress-fraction">
          {completed}/{steps.length}
        </span>
      </div>

      <div
        className="iv-progress-track"
        role="progressbar"
        aria-label="Workspace setup progress"
        aria-valuemin={0}
        aria-valuemax={steps.length}
        aria-valuenow={completed}
      >
        <span style={{ width: `${progress}%` }} />
      </div>

      <ol className="iv-steps">
        {steps.map((step) => (
          <StepItem key={step.label} {...step} />
        ))}
      </ol>
    </section>
  );
}

function TeamCard({
  members,
  meId,
}: {
  members: MemberOut[];
  meId: string;
}) {
  return (
    <section className="iv-panel iv-team-panel">
      <div className="iv-panel-top">
        <div className="iv-panel-icon">
          <UsersRound size={19} />
        </div>
        <span className="iv-panel-kicker">COLLABORATION</span>
      </div>

      <div className="iv-panel-title-row">
        <div>
          <h3>Your team</h3>
          <p>The people shaping your innovation decisions.</p>
        </div>
        <Link href="/team" className="iv-text-link">
          View all <ArrowUpRight size={15} />
        </Link>
      </div>

      {members.length > 0 ? (
        <ul className="iv-team-list">
          {members.slice(0, TEAM_PREVIEW).map((member) => {
            const initials = member.name
              .trim()
              .split(/\s+/)
              .slice(0, 2)
              .map((part) => part[0]?.toUpperCase() ?? "")
              .join("");

            return (
              <li key={member.id} className="iv-team-member">
                <span className="iv-team-avatar" aria-hidden="true">
                  {initials || "U"}
                </span>
                <span className="iv-team-member-copy">
                  <span className="iv-team-member-name">
                    {member.name}
                    {member.user_id === meId && (
                      <span className="iv-you-label"> (you)</span>
                    )}
                  </span>
                  <span className="iv-team-member-desc">
                    Organisation member
                  </span>
                </span>
                <span className="iv-role-pill">
                  {roleLabel(member.role)}
                </span>
              </li>
            );
          })}
        </ul>
      ) : (
        <div className="iv-empty-team">
          <UsersRound size={26} />
          <p>No team members to show yet.</p>
        </div>
      )}

      {members.length > TEAM_PREVIEW && (
        <p className="iv-team-extra">
          +{members.length - TEAM_PREVIEW} additional members
        </p>
      )}

      <Link href="/team" className="iv-panel-footer-link">
        <span>Manage team</span>
        <ArrowRight size={17} />
      </Link>
    </section>
  );
}

function ReadinessCard({
  latest,
  manage,
  consultant = false,
}: {
  latest: AssessmentSummaryOut | undefined;
  manage: boolean;
  consultant?: boolean;
}) {
  let status = "Not started";
  let description =
    "Evaluate readiness across 60 questions and 12 dimensions of innovation.";
  let actionLabel = manage ? "Start assessment" : "View assessments";
  let href = "/readiness";
  let score: ReactNode = null;
  let showAction = true;

  if (!latest) {
    if (consultant) {
      description =
        "The final readiness result will appear when the organisation completes its assessment.";
      showAction = false;
    } else if (!manage) {
      description =
        "An owner or admin can start the readiness assessment for your team.";
    }
  } else if (latest.status === "final") {
    status = "Completed";
    description = `Finalised ${formatDate(
      latest.finalised_at ?? latest.created_at,
    )}.`;

    score = (
      <div className="iv-readiness-score">
        <strong>{latest.total}</strong>
        <span>/ 300</span>
        <span className="iv-score-band">{latest.band_name}</span>
      </div>
    );

    actionLabel = "View results";
    href = assessmentHref(latest, manage);
  } else if (latest.status === "consensus") {
    status = "Team alignment";
    description = manage
      ? `${latest.submitted_count} team submissions received. Agree on the final answers to complete the assessment.`
      : "The team's answers are being agreed. Results will appear when finalised.";

    if (manage) {
      actionLabel = "Agree answers";
      href = assessmentHref(latest, manage);
    } else {
      showAction = false;
    }
  } else {
    status = "Collecting answers";
    description = `${latest.submitted_count} team submissions received.`;

    if (latest.my_status === "submitted") {
      description += " Your answers are submitted.";
    } else if (latest.my_status === "in_progress") {
      description += " Your answers are in progress.";
    } else if (latest.my_status === "not_started") {
      description += " You have not started yet.";
    }

    href = assessmentHref(latest, manage);

    if (latest.my_status && latest.my_status !== "submitted") {
      actionLabel = "Continue assessment";
    } else if (manage) {
      actionLabel = "View team progress";
    } else {
      showAction = false;
    }
  }

  return (
    <section className="iv-readiness-panel">
      <div className="iv-readiness-content">
        <div className="iv-readiness-overline">
          <span className="iv-readiness-symbol">
            <ClipboardCheck size={20} />
          </span>
          <span>INNOVATION READINESS</span>
        </div>

        <div className="iv-readiness-main">
          <div>
            <h3>Know where you stand.</h3>
            <p>{description}</p>
            <span className="iv-readiness-status">
              <span className="iv-status-dot" />
              {status}
            </span>
          </div>

          {score}
        </div>

        {showAction && (
          <div className="iv-readiness-actions">
            <ActionLink href={href} primary>
              {actionLabel}
            </ActionLink>
          </div>
        )}
      </div>

      <div className="iv-readiness-visual" aria-hidden="true">
        <div className="iv-orbit iv-orbit-one" />
        <div className="iv-orbit iv-orbit-two" />
        <div className="iv-orbit iv-orbit-three" />
        <div className="iv-orbit-center">
          <Compass size={49} strokeWidth={1.05} />
        </div>
        <div className="iv-orbit-node iv-orbit-node-one">
          <Target size={17} />
        </div>
        <div className="iv-orbit-node iv-orbit-node-two">
          <Sparkles size={16} />
        </div>
        <div className="iv-orbit-node iv-orbit-node-three">
          <CheckCircle2 size={16} />
        </div>
      </div>
    </section>
  );
}

function QuickActions({ manage }: { manage: boolean }) {
  const actions = [
    ...(manage
      ? [
        {
          label: "Invite a member",
          desc: "Grow your team",
          href: "/team",
          icon: UsersRound,
        },
        {
          label: "Organisation settings",
          desc: "Manage your profile",
          href: "/organisation",
          icon: Settings2,
        },
        {
          label: "Consultant access",
          desc: "Manage external access",
          href: "/consultants",
          icon: ShieldCheck,
        },
      ]
      : [
        {
          label: "Explore your team",
          desc: "See team members",
          href: "/team",
          icon: UsersRound,
        },
      ]),
    {
      label: "Account settings",
      desc: "Manage your account",
      href: "/account",
      icon: Settings2,
    },
  ];

  return (
    <section className="iv-quick-section">
      <SectionHeading
        eyebrow="YOUR WORKSPACE"
        title="Quick actions"
        description="Everything you need, just one click away."
      />

      <div className="iv-quick-grid">
        {actions.map((action) => {
          const Icon = action.icon;
          return (
            <Link
              key={action.href}
              href={action.href}
              className="iv-quick-card"
            >
              <span className="iv-quick-icon">
                <Icon size={21} strokeWidth={1.7} />
              </span>
              <span className="iv-quick-copy">
                <strong>{action.label}</strong>
                <small>{action.desc}</small>
              </span>
              <ArrowUpRight size={17} className="iv-quick-arrow" />
            </Link>
          );
        })}
      </div>
    </section>
  );
}

function WelcomeBanner({
  name,
  organisation,
  role,
  archived = false,
}: {
  name: string;
  organisation?: string;
  role?: string;
  archived?: boolean;
}) {
  return (
    <section className="iv-welcome">
      <div className="iv-welcome-copy">
        <div className="iv-welcome-eyebrow">
          <span className="iv-gold-dot" />
          INNOVATION INTELLIGENCE WORKSPACE
        </div>

        <h1>Welcome back, {name}<span className="iv-gold-period">.</span></h1>

        <p>
          {organisation
            ? `Your ${organisation} workspace is ready. Turn ideas into informed decisions.`
            : "Start your innovation journey by setting up your organisation."}
        </p>

        {organisation && (
          <div className="iv-welcome-tags">
            <span>
              <Building2 size={14} />
              {organisation}
            </span>
            {role && (
              <span>
                <BadgeCheck size={14} />
                {role}
              </span>
            )}
            {archived && <span>Archived · View only</span>}
          </div>
        )}
      </div>

      <div className="iv-welcome-decoration" aria-hidden="true">
        <div className="iv-welcome-ring">
          <Compass size={88} strokeWidth={0.75} />
        </div>
      </div>
    </section>
  );
}

/**
 * Signed-in dashboard.
 * All statistics and assessment details are sourced from the existing API.
 */
export function DashboardPage() {
  const { me } = useMe();
  const activeOrgId = me.active_organisation_id;
  // Without the AI nothing about ideas or the IQ is shown, so it is not asked for either.
  const aiEnabled = me.ai_enabled;
  const [state, setState] = useState<State>({ kind: "loading" });
  const [selecting, setSelecting] = useState(false);
  const [selectError, setSelectError] = useState<string | null>(null);

  // Bumped on every load, so a late answer to an idea pick made in another organisation
  // (or before a newer pick) is dropped instead of landing on this one.
  const generation = useRef(0);

  useEffect(() => {
    if (!activeOrgId) return;
    let cancelled = false;
    generation.current += 1;
    async function load() {
      setState({ kind: "loading" });
      setSelectError(null);
      setSelecting(false);
      try {
        const org = await getOrganisation();
        const consultant = org.role === "consultant";
        const manage = canManage(org.role) && org.status === "active";
        const [members, invitations, grants, assessments, ideas, dashboard] = await Promise.all([
          consultant ? Promise.resolve([]) : listMembers(),
          manage ? listInvitations() : Promise.resolve([]),
          manage ? listGrants() : Promise.resolve([]),
          listAssessments(),
          aiEnabled ? listIdeas() : Promise.resolve([]),
          getDashboard(),
        ]);
        if (!cancelled) {
          setState({
            kind: "ready",
            org,
            members,
            invitations,
            grants,
            assessments,
            ideas,
            dashboard: aiEnabled ? dashboard : { ...dashboard, iq: null, ideas: [] },
          });
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
  }, [activeOrgId, aiEnabled]);

  const firstName = me.name.trim().split(/\s+/)[0] || me.name;

  /** Show another idea's IQ: only the scores are fetched again. */
  async function selectIdea(ideaId: string) {
    generation.current += 1;
    const mine = generation.current;
    setSelecting(true);
    setSelectError(null);
    try {
      const dashboard = await getDashboard(ideaId);
      if (generation.current !== mine) return;
      setState((current) => (current.kind === "ready" ? { ...current, dashboard } : current));
    } catch (err) {
      if (generation.current !== mine) return;
      setSelectError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      if (generation.current === mine) setSelecting(false);
    }
  }

  if (!activeOrgId) {
    return (
      <div className="iv-dashboard">
        <WelcomeBanner name={firstName} />

        <section className="iv-panel iv-no-org">
          <span className="iv-panel-icon">
            <Building2 size={22} />
          </span>
          <h2>Let&apos;s build your innovation workspace.</h2>
          <p>
            Create an organisation to collaborate with your team,
            evaluate readiness, and make better decisions.
          </p>

          <div className="iv-no-org-actions">
            <ActionLink href="/organisations/new" primary>
              Create an organisation
            </ActionLink>

            {me.consultant_organisations.length > 0 && (
              <ActionLink href="/consultant-access">
                Organisations you consult for
              </ActionLink>
            )}
          </div>
        </section>
      </div>
    );
  }

  if (state.kind === "loading" || (
    state.kind === "ready" && state.org.id !== activeOrgId
  )) {
    return (
      <div className="iv-dashboard">
        <Loading>Loading your dashboard...</Loading>
      </div>
    );
  }

  if (state.kind === "error") {
    return <Alert tone="error">{state.message}</Alert>;
  }

  const { org } = state;

  if (org.role === "consultant") {
    const access = me.consultant_organisations.find(
      (o) => o.organisation_id === org.id,
    );

    return (
      <div className="iv-dashboard">
        <WelcomeBanner
          name={firstName}
          organisation={org.name}
          role="Consultant"
        />

        <Alert tone="info">
          You have read-only consultant access to {org.name}
          {access
            ? ` until ${formatDate(access.access_ends_at)}`
            : ""}.
        </Alert>

        {selectError && <Alert tone="error">{selectError}</Alert>}

        <ScoresPanel
          dashboard={state.dashboard}
          onSelectIdea={(id) => void selectIdea(id)}
          selecting={selecting}
          readinessFallback={
            <ReadinessCard
              latest={state.assessments[0]}
              manage={false}
              consultant
            />
          }
          iqFallback={
            aiEnabled
              ? <IdeasCard ideas={state.ideas} canAdd={false} />
              : null
          }
        />

        <section className="iv-panel iv-no-org">
          <span className="iv-panel-icon">
            <ShieldCheck size={22} />
          </span>
          <h2>Your consulting access</h2>
          <p>
            View the organisations that have granted you access,
            and manage invitations.
          </p>
          <div className="iv-no-org-actions">
            <ActionLink href="/consultant-access" primary>
              My access
            </ActionLink>
          </div>
        </section>
      </div>
    );
  }

  const manage =
    canManage(org.role) && org.status === "active";

  const waitingInvitations = state.invitations.filter(
    (invitation) => !invitation.expired,
  );

  const activeGrants = state.grants.filter(
    (grant) => grant.status === "active",
  );

  const openGrants = state.grants.filter(
    (grant) =>
      grant.status === "active" || grant.status === "waiting",
  );

  const latest = state.assessments[0];
  const isArchived = org.status === "archived";

  return (
    <div className="iv-dashboard">
      <WelcomeBanner
        name={firstName}
        organisation={org.name}
        role={roleWithArticle(org.role)}
        archived={isArchived}
      />

      {isArchived && (
        <Alert tone="info">
          This organisation is archived, so it is view-only.
        </Alert>
      )}

      <section aria-label="At a glance">
        <SectionHeading
          eyebrow="OVERVIEW"
          title="At a glance"
          description="A clear view of your innovation workspace."
        />

        <div className="iv-metrics-grid">
          <MetricCard
            icon={UsersRound}
            label="Team members"
            value={state.members.length}
            hint="Current members"
            href="/team"
          />

          {manage ? (
            <MetricCard
              icon={Mail}
              label="Pending invitations"
              value={waitingInvitations.length}
              hint="Awaiting acceptance"
              href="/team"
            />
          ) : (
            <MetricCard
              icon={ClipboardCheck}
              label="Assessments"
              value={state.assessments.length}
              hint="Available assessments"
              href="/readiness"
            />
          )}

          {manage ? (
            <MetricCard
              icon={ShieldCheck}
              label="Consultant access"
              value={activeGrants.length}
              hint={
                openGrants.length > activeGrants.length
                  ? `${openGrants.length - activeGrants.length
                  } waiting to accept`
                  : "Active access grants"
              }
              href="/consultants"
            />
          ) : (
            <MetricCard
              icon={FileCheck2}
              label="Readiness"
              value={
                latest?.status === "final"
                  ? "Complete"
                  : latest
                    ? "In progress"
                    : "Not started"
              }
              hint="Latest assessment"
              href="/readiness"
            />
          )}

          <MetricCard
            icon={Wallet}
            label="Currency"
            value={org.currency}
            hint="Organisation currency"
            href={manage ? "/organisation" : undefined}
          />
        </div>
      </section>

      {selectError && <Alert tone="error">{selectError}</Alert>}

      <ScoresPanel
        dashboard={state.dashboard}
        onSelectIdea={(id) => void selectIdea(id)}
        selecting={selecting}
        readinessFallback={
          <ReadinessCard latest={latest} manage={manage} />
        }
        iqFallback={
          aiEnabled ? (
            <IdeasCard
              ideas={state.ideas}
              canAdd={org.role !== "investor" && org.status === "active"}
            />
          ) : null
        }
      />

      {/* The fallbacks above show only while there is no score. Once there is one, a
          newer assessment still needs its card to be answered, and ideas their entry point. */}
      {state.dashboard.readiness && latest?.status !== "final" && (
        <ReadinessCard latest={latest} manage={manage} />
      )}
      {state.dashboard.iq && (
        <IdeasCard
          ideas={state.ideas}
          canAdd={org.role !== "investor" && org.status === "active"}
        />
      )}

      <section>
        <SectionHeading
          eyebrow="WORKSPACE PROGRESS"
          title={manage ? "Build your momentum" : "Your organisation"}
          description={
            manage
              ? "Keep your team aligned and your innovation strategy moving."
              : "Stay connected with your team's innovation journey."
          }
        />

        <div className="iv-content-grid">
          {manage ? (
            <SetupCard
              org={org}
              members={state.members}
              grants={state.grants}
              assessments={state.assessments}
              ideas={state.ideas}
              aiEnabled={aiEnabled}
            />
          ) : (
            <section className="iv-panel iv-member-panel">
              <div className="iv-panel-top">
                <div className="iv-panel-icon">
                  <BadgeCheck size={19} />
                </div>
                <span className="iv-panel-kicker">
                  YOUR MEMBERSHIP
                </span>
              </div>

              <h3>You&apos;re part of the team.</h3>
              <p>
                Work together with your organisation to assess
                opportunities and improve innovation readiness.
              </p>

              <div className="iv-member-info">
                <span>Organisation</span>
                <strong>{org.name}</strong>
              </div>
              <div className="iv-member-info">
                <span>Your role</span>
                <strong>{roleLabel(org.role)}</strong>
              </div>

              <ActionLink href="/readiness" primary>
                Explore readiness
              </ActionLink>
            </section>
          )}

          <TeamCard members={state.members} meId={me.id} />
        </div>
      </section>

      <QuickActions manage={manage} />
    </div>
  );
}

function IdeasCard({ ideas, canAdd }: { ideas: IdeaSummaryOut[]; canAdd: boolean }) {
  const scored = ideas.filter(
    (i) => i.latest_assessment?.status === "confirmed" && i.latest_assessment.iq !== null,
  );
  const best = [...scored].sort(
    (a, b) => Number(b.latest_assessment?.iq) - Number(a.latest_assessment?.iq),
  )[0];
  return (
    <Card>
      <CardHeader
        title="Ideas"
        actions={
          <Link href="/ideas" className="text-sm font-medium text-primary hover:underline">
            View all
          </Link>
        }
      />
      <div className="mt-3 text-sm text-neutral-600">
        {ideas.length === 0 ? (
          canAdd
            ? "Describe an idea and the AI proposes a 1 to 10 score for each of the 12 dimensions. You confirm; the IQ is out of 100."
            : "Ideas added by the team appear here with their IQ."
        ) : (
          <div className="flex flex-wrap items-end gap-x-8 gap-y-3">
            <div>
              <Eyebrow>Ideas</Eyebrow>
              <p className="mt-1 text-2xl font-semibold text-neutral-900 tabular-nums">
                {ideas.length}
                <span className="ml-1 text-sm font-normal text-neutral-500">
                  {scored.length} scored
                </span>
              </p>
            </div>
            {best?.latest_assessment && (
              <div>
                <Eyebrow>Highest IQ</Eyebrow>
                <p className="mt-1 text-2xl font-semibold text-neutral-900 tabular-nums">
                  {best.latest_assessment.iq}
                  <span className="ml-1 text-sm font-normal text-neutral-500">/ 100</span>
                </p>
                <p className="text-xs text-neutral-600">{best.title}</p>
              </div>
            )}
          </div>
        )}
      </div>
      {canAdd && (
        <div className="mt-4">
          <ActionLink href="/ideas/new" primary={ideas.length === 0}>
            Add an idea
          </ActionLink>
        </div>
      )}
    </Card>
  );
}
