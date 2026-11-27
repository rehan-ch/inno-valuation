
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  CalendarDays,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  Clock3,
  Compass,
  FileCheck2,
  Layers3,
  Plus,
  ShieldCheck,
  Sparkles,
  Target,
  UsersRound,
} from "lucide-react";

import { useMe } from "@/components/app/me-context";
import { Alert } from "@/components/ui/Alert";
import { Loading } from "@/components/ui/Loading";
import { ApiError } from "@/lib/api/client";
import {
  assessmentHref,
  listAssessments,
  startAssessment,
} from "@/lib/api/readiness";
import type { AssessmentSummaryOut } from "@/lib/api/types";
import { formatDate } from "@/lib/format";
import { useSubmit } from "@/lib/forms";
import { activeMembership, canManage } from "@/lib/roles";

import { MY_STATUS_LABELS, STATUS_LABELS } from "./status";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; assessments: AssessmentSummaryOut[] };

function StatusIcon({ status }: {
  status: AssessmentSummaryOut["status"];
}) {
  if (status === "final") return <CheckCircle2 size={14} />;
  if (status === "consensus") return <UsersRound size={14} />;
  if (status === "collecting") return <Clock3 size={14} />;
  return <ClipboardCheck size={14} />;
}

/** What this person can do with the assessment, as the row's and the hero's link text. */
function actionLabel(a: AssessmentSummaryOut, manage: boolean): string {
  if (a.status === "final") return "See the result";
  if (a.status === "consensus" && manage) return "Agree the answers";
  if (a.my_status && a.my_status !== "submitted" && a.status === "collecting") {
    return "Answer the questions";
  }
  return "Open";
}

function AssessmentCard({
  assessment,
  manage,
  index,
}: {
  assessment: AssessmentSummaryOut;
  manage: boolean;
  index: number;
}) {
  const a = assessment;
  const isFinal = a.status === "final";

  const action = actionLabel(a, manage);

  const personalStatus = isFinal && a.total !== null
    ? `${a.total} out of 300 · ${a.band_name ?? ""}`
    : a.my_status
      ? MY_STATUS_LABELS[a.my_status]
      : `${a.submitted_count} submitted so far`;

  return (
    <li className="iv-rd-assessment">
      <div className="iv-rd-assessment-icon">
        {isFinal ? (
          <FileCheck2 size={23} strokeWidth={1.6} />
        ) : (
          <ClipboardCheck size={23} strokeWidth={1.6} />
        )}
      </div>

      <div className="iv-rd-assessment-content">
        <div className="iv-rd-assessment-top">
          <span className="iv-rd-assessment-index">
            ASSESSMENT {String(index + 1).padStart(2, "0")}
          </span>

          <span className={`iv-rd-status iv-rd-status-${a.status}`}>
            <StatusIcon status={a.status} />
            {STATUS_LABELS[a.status]}
          </span>
        </div>

        <h3 className="iv-rd-assessment-title">
          {isFinal
            ? "Completed readiness assessment"
            : a.status === "consensus"
              ? "Team consensus in progress"
              : a.status === "collecting"
                ? "Innovation readiness assessment"
                : "Assessment draft"}
        </h3>

        <div className="iv-rd-assessment-meta">
          <span>
            <CalendarDays size={14} aria-hidden="true" />
            Started {formatDate(a.started_at ?? a.created_at)}
          </span>
          {a.created_by_name && (
            <span>
              <UsersRound size={14} aria-hidden="true" />
              by {a.created_by_name}
            </span>
          )}
        </div>

        <p className="iv-rd-personal-status">
          {personalStatus}
        </p>
      </div>

      <Link
        href={assessmentHref(a, manage)}
        className="iv-rd-assessment-link"
      >
        {action}
        <ArrowUpRight size={17} aria-hidden="true" />
      </Link>
    </li>
  );
}

export function ReadinessListPage() {
  const { me } = useMe();
  const router = useRouter();
  const activeOrgId = me.active_organisation_id;
  const membership = activeMembership(me);

  const manage =
    membership !== null &&
    canManage(membership.role) &&
    membership.organisation_status === "active";

  const [state, setState] = useState<State>({
    kind: "loading",
  });

  const { busy, error, run } = useSubmit();

  useEffect(() => {
    if (!activeOrgId) return;

    let cancelled = false;

    async function load() {
      setState({ kind: "loading" });

      try {
        const assessments = await listAssessments();

        if (!cancelled) {
          setState({ kind: "ready", assessments });
        }
      } catch (err: unknown) {
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

  async function handleStart() {
    const started = await run(() => startAssessment());
    if (started) {
      router.push(`/readiness/${started.id}`);
    }
  }

  if (!activeOrgId) {
    return (
      <div className="iv-readiness">
        <div className="iv-rd-empty">
          <Compass size={40} />
          <h1>Select your workspace</h1>
          <p>
            Choose an organisation above to explore
            its innovation readiness assessments.
          </p>
        </div>
      </div>
    );
  }

  if (state.kind === "loading") {
    return <Loading>Loading assessments...</Loading>;
  }

  if (state.kind === "error") {
    return <Alert tone="error">{state.message}</Alert>;
  }

  const { assessments } = state;
  const open = assessments.find((a) => a.status !== "final");
  // Only someone with something to do is asked to continue; watchers, and members who
  // have already submitted, are offered a look instead.
  const openAction = open ? actionLabel(open, manage) : null;
  const completed = assessments.filter(
    (a) => a.status === "final",
  ).length;

  return (
    <div className="iv-readiness">
      {/* Premium introduction */}
      <section className="iv-rd-hero">
        <div className="iv-rd-hero-content">
          <div className="iv-rd-eyebrow">
            <span className="iv-rd-eyebrow-dot" />
            INNOVATION INTELLIGENCE
          </div>

          <h1>
            Understand your
            <span> innovation potential.</span>
          </h1>

          <p className="iv-rd-hero-description">
            Turn insight into action. Understand your
            organisation&apos;s readiness across 12
            dimensions, align your team, and make
            more informed innovation decisions.
          </p>

          <div className="iv-rd-hero-features">
            <span>
              <Layers3 size={15} />
              12 dimensions
            </span>
            <span>
              <ClipboardCheck size={15} />
              60 questions
            </span>
            <span>
              <Target size={15} />
              300-point scoring
            </span>
          </div>

          {manage && !open && (
            <button
              type="button"
              className="iv-rd-hero-action"
              disabled={busy}
              onClick={() => void handleStart()}
            >
              <Plus size={19} />
              {busy
                ? "Starting assessment..."
                : "Start a readiness assessment"}
              <ArrowRight size={18} />
            </button>
          )}

          {open && (
            <Link
              className="iv-rd-hero-action"
              href={assessmentHref(open, manage)}
            >
              {openAction === "Open" ? "View the assessment" : openAction}
              <ArrowRight size={18} />
            </Link>
          )}
        </div>

        <div className="iv-rd-hero-visual" aria-hidden="true">
          <div className="iv-rd-orbit iv-rd-orbit-one" />
          <div className="iv-rd-orbit iv-rd-orbit-two" />
          <div className="iv-rd-orbit iv-rd-orbit-three" />

          <div className="iv-rd-orbit-center">
            <Compass size={62} strokeWidth={1.05} />
          </div>

          <div className="iv-rd-orbit-node iv-rd-node-top">
            <Sparkles size={19} />
          </div>
          <div className="iv-rd-orbit-node iv-rd-node-right">
            <Target size={19} />
          </div>
          <div className="iv-rd-orbit-node iv-rd-node-bottom">
            <ShieldCheck size={19} />
          </div>

          <span className="iv-rd-orbit-caption">
            NAVIGATE · MEASURE · INNOVATE
          </span>
        </div>
      </section>

      {error && <Alert tone="error">{error.message}</Alert>}

      {/* Live overview */}
      <section aria-label="Assessment overview">
        <div className="iv-rd-section-heading">
          <div>
            <span className="iv-rd-section-eyebrow">OVERVIEW</span>
            <h2>Your readiness at a glance</h2>
            <p>
              A clearer view of your innovation
              assessment journey.
            </p>
          </div>
        </div>

        <div className="iv-rd-metrics">
          <div className="iv-rd-metric">
            <div className="iv-rd-metric-icon">
              <Layers3 size={21} />
            </div>
            <span className="iv-rd-metric-label">
              Innovation dimensions
            </span>
            <strong>12</strong>
            <span className="iv-rd-metric-detail">
              Structured framework
            </span>
          </div>

          <div className="iv-rd-metric">
            <div className="iv-rd-metric-icon">
              <ClipboardCheck size={21} />
            </div>
            <span className="iv-rd-metric-label">
              Assessment questions
            </span>
            <strong>60</strong>
            <span className="iv-rd-metric-detail">
              5 questions per dimension
            </span>
          </div>

          <div className="iv-rd-metric">
            <div className="iv-rd-metric-icon">
              <BarChart3 size={21} />
            </div>
            <span className="iv-rd-metric-label">
              Total assessments
            </span>
            <strong>{assessments.length}</strong>
            <span className="iv-rd-metric-detail">
              Assessment records
            </span>
          </div>

          <div className="iv-rd-metric">
            <div className="iv-rd-metric-icon">
              <CheckCircle2 size={21} />
            </div>
            <span className="iv-rd-metric-label">
              Completed
            </span>
            <strong>{completed}</strong>
            <span className="iv-rd-metric-detail">
              Finalised assessments
            </span>
          </div>
        </div>
      </section>

      {/* Assessment history */}
      <section aria-labelledby="iv-rd-assessments-title">
        <div className="iv-rd-section-heading">
          <div>
            <span className="iv-rd-section-eyebrow">
              YOUR ASSESSMENTS
            </span>
            <h2 id="iv-rd-assessments-title">
              Assessment workspace
            </h2>
            <p>
              Continue an assessment or review
              previously completed results.
            </p>
          </div>

          {manage && !open && (
            <button
              type="button"
              className="iv-rd-new-button"
              disabled={busy}
              onClick={() => void handleStart()}
            >
              <Plus size={17} />
              {busy ? "Starting..." : "New assessment"}
            </button>
          )}
        </div>

        {assessments.length === 0 ? (
          <div className="iv-rd-empty">
            <div className="iv-rd-empty-icon">
              <ClipboardCheck size={30} />
            </div>
            <h3>Your innovation journey begins here.</h3>
            <p>
              {manage
                ? "Start your first assessment to understand your organisation's innovation readiness."
                : "An owner or admin can start an assessment. Once started, it will appear here."}
            </p>
            {manage && (
              <button
                type="button"
                className="iv-rd-hero-action"
                disabled={busy}
                onClick={() => void handleStart()}
              >
                Create your first assessment
                <ArrowRight size={17} aria-hidden="true" />
              </button>
            )}
          </div>
        ) : (
          <ul className="iv-rd-assessment-list">
            {assessments.map((assessment, index) => (
              <AssessmentCard
                key={assessment.id}
                assessment={assessment}
                manage={manage}
                index={index}
              />
            ))}
          </ul>
        )}
      </section>

      {/* Methodology information */}
      <section className="iv-rd-info">
        <div className="iv-rd-info-icon">
          <ShieldCheck size={22} />
        </div>
        <div>
          <h2>A structured approach to innovation.</h2>
          <p>
            Every assessment follows the same
            framework: individual responses,
            team agreement, and a final readiness
            result out of 300.
          </p>
        </div>
        <ChevronRight size={22} className="iv-rd-info-arrow" />
      </section>
    </div>
  );
}
