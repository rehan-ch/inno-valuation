"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";

import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button, buttonClass } from "@/components/ui/Button";
import { Card, CardDescription, CardHeader, CardTitle, Eyebrow, PageHeader } from "@/components/ui/Card";
import { ConfirmButton } from "@/components/ui/ConfirmButton";
import { Loading } from "@/components/ui/Loading";
import { ApiError } from "@/lib/api/client";
import { archiveIdea, getIdea, requestAssessment, restoreIdea } from "@/lib/api/ideas";
import type { AssessmentBriefOut, IdeaOut } from "@/lib/api/types";
import { formatDate, formatDateTime } from "@/lib/format";
import { useSubmit } from "@/lib/forms";
import { formatMoney } from "@/lib/money";

import { ASSESSMENT_STATUS_LABELS, IDEA_STATUS_LABELS, IDEA_STATUS_TONES, STAGE_LABELS, assessmentLabel } from "./status";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; idea: IdeaOut };

/** One idea: what the team wrote, its investment, and where its scoring stands. */
export function IdeaPage({ ideaId }: { ideaId: string }) {
  const router = useRouter();
  const [state, setState] = useState<State>({ kind: "loading" });
  const action = useSubmit();

  useEffect(() => {
    let cancelled = false;
    getIdea(ideaId)
      .then((idea) => {
        if (!cancelled) setState({ kind: "ready", idea });
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setState({
            kind: "error",
            message: err instanceof ApiError ? err.message : "Something went wrong.",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [ideaId]);

  if (state.kind === "loading") return <Loading>Loading the idea...</Loading>;
  if (state.kind === "error") return <Alert tone="error">{state.message}</Alert>;

  const { idea } = state;
  const latest = idea.latest_assessment;
  const update = (next: IdeaOut) => setState({ kind: "ready", idea: next });

  async function score() {
    const assessment = await action.run(() => requestAssessment(idea.id));
    if (assessment) router.push(`/ideas/${idea.id}/assessments/${assessment.id}`);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={idea.title}
        description={
          <>
            {STAGE_LABELS[idea.stage]}
            {idea.created_by_name ? ` · added by ${idea.created_by_name}` : ""} on{" "}
            {formatDate(idea.created_at)}
          </>
        }
        actions={
          <>
            <Badge tone={IDEA_STATUS_TONES[idea.status]}>{IDEA_STATUS_LABELS[idea.status]}</Badge>
            {idea.archived && <Badge>Archived</Badge>}
            <Link href="/ideas" className="text-sm font-medium text-primary hover:underline">
              All ideas
            </Link>
          </>
        }
      />
      {action.error && <Alert tone="error">{action.error.message}</Alert>}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader
              title="About this idea"
              actions={
                idea.can_change && !idea.archived && idea.status !== "submitted" ? (
                  <Link href={`/ideas/${idea.id}/edit`} className={buttonClass("secondary", "sm")}>
                    Edit
                  </Link>
                ) : null
              }
            />
            <dl className="mt-4 space-y-4">
              <Field label="Summary">{idea.summary}</Field>
              {idea.problem && <Field label="Problem or opportunity">{idea.problem}</Field>}
              {idea.target_market && <Field label="Target market">{idea.target_market}</Field>}
              {idea.uniqueness && <Field label="What makes it different">{idea.uniqueness}</Field>}
              {idea.team && <Field label="Team">{idea.team}</Field>}
              {idea.risks && <Field label="Risks">{idea.risks}</Field>}
            </dl>
          </Card>

          <Card>
            <CardTitle>Scoring history</CardTitle>
            <CardDescription>
              Every scoring is kept. A confirmed IQ never changes; scoring again adds a new one.
            </CardDescription>
            {idea.assessments.length === 0 ? (
              <p className="mt-3 text-sm text-neutral-600">Not scored yet.</p>
            ) : (
              <ul className="mt-3 divide-y divide-neutral-100">
                {idea.assessments.map((a) => (
                  <li key={a.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 py-2.5 text-sm">
                    <span className="min-w-0 flex-1">
                      <span className="block text-neutral-900">
                        {ASSESSMENT_STATUS_LABELS[a.status]}
                        {a.status === "confirmed" && a.iq !== null && (
                          <span className="ml-2 font-medium tabular-nums">IQ {a.iq} / 100</span>
                        )}
                      </span>
                      <span className="block text-xs text-neutral-500">
                        Requested {formatDateTime(a.requested_at)}
                        {a.confirmed_at ? ` · confirmed ${formatDateTime(a.confirmed_at)}` : ""}
                        {a.sample ? " · sample" : ""}
                      </span>
                    </span>
                    <Link
                      href={`/ideas/${idea.id}/assessments/${a.id}`}
                      className="font-medium text-primary hover:underline"
                    >
                      {a.status === "confirmed" ? "See the IQ" : "Open"}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>

        <div className="space-y-6">
          <ScoringCard
            idea={idea}
            latest={latest}
            busy={action.busy}
            onScore={() => void score()}
          />
          <Card>
            <CardTitle>Investment</CardTitle>
            <dl className="mt-3 space-y-3">
              <div>
                <Eyebrow>Planned investment</Eyebrow>
                <dd className="mt-1 text-lg font-semibold text-neutral-900 tabular-nums">
                  {idea.investment ? formatMoney(idea.investment, idea.currency) : "Not given"}
                </dd>
              </div>
              <div>
                <Eyebrow>Expected value</Eyebrow>
                <dd className="mt-1 text-sm text-neutral-900 tabular-nums">
                  {idea.expected_value ? formatMoney(idea.expected_value, idea.currency) : "Not given"}
                </dd>
              </div>
              <div>
                <Eyebrow>Currency</Eyebrow>
                <dd className="mt-1 text-sm text-neutral-900">{idea.currency}</dd>
              </div>
            </dl>
          </Card>
          {idea.can_archive && (
            <Card>
              <CardTitle>{idea.archived ? "Archived" : "Archive"}</CardTitle>
              <CardDescription>
                {idea.archived
                  ? "This idea is hidden from the list. Its scorings are kept."
                  : "Hide this idea from the list. Its scorings are kept and it can be restored."}
              </CardDescription>
              <div className="mt-4">
                {idea.archived ? (
                  <Button
                    variant="secondary"
                    busy={action.busy}
                    onClick={() => void action.run(() => restoreIdea(idea.id)).then((r) => r && update(r))}
                  >
                    Restore
                  </Button>
                ) : (
                  <ConfirmButton
                    label="Archive this idea"
                    confirmLabel="Yes, archive"
                    busy={action.busy}
                    onConfirm={() => void action.run(() => archiveIdea(idea.id)).then((r) => r && update(r))}
                  />
                )}
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-[13px] font-medium text-neutral-800">{label}</dt>
      <dd className="mt-1 text-sm whitespace-pre-line text-neutral-700">{children}</dd>
    </div>
  );
}

function ScoringCard({
  idea,
  latest,
  busy,
  onScore,
}: {
  idea: IdeaOut;
  latest: AssessmentBriefOut | null;
  busy: boolean;
  onScore: () => void;
}) {
  const href = latest ? `/ideas/${idea.id}/assessments/${latest.id}` : null;
  const canScore = idea.can_change && !idea.archived;
  let body: ReactNode;
  let action: ReactNode = null;

  if (!latest || latest.status === "superseded") {
    body = canScore
      ? "Send the idea for scoring. The AI proposes a 1 to 10 score for each of the 12 dimensions, with its reasons; you confirm or change every one."
      : "Not scored yet.";
    if (canScore) {
      action = (
        <Button busy={busy} onClick={onScore}>
          Score this idea
        </Button>
      );
    }
  } else if (latest.status === "confirmed") {
    body = (
      <div>
        <Eyebrow>Innovation Quotient</Eyebrow>
        <p className="mt-1 text-3xl font-semibold text-neutral-900 tabular-nums">
          {latest.iq}
          <span className="ml-1 text-base font-normal text-neutral-500">/ 100</span>
        </p>
        <p className="mt-1 text-sm text-neutral-600">
          {latest.vfm_per_point && latest.currency
            ? `${formatMoney(latest.vfm_per_point, latest.currency)} per innovation point.`
            : "Value for Money not calculable."}
          {latest.confirmed_at ? ` Confirmed ${formatDate(latest.confirmed_at)}.` : ""}
        </p>
      </div>
    );
    action = (
      <div className="flex flex-wrap gap-2">
        <Link href={href!} className={buttonClass("primary")}>
          See the IQ
        </Link>
        {canScore && (
          <Button variant="secondary" busy={busy} onClick={onScore}>
            Score again
          </Button>
        )}
      </div>
    );
  } else if (latest.proposal_status === "pending") {
    body = "The AI is reading the idea and proposing a score for each dimension. This takes a minute or two.";
    action = (
      <Link href={href!} className={buttonClass("secondary")}>
        Watch the proposal
      </Link>
    );
  } else if (latest.proposal_status === "failed") {
    body = "The proposal could not be made this time.";
    if (canScore) {
      action = (
        <Button busy={busy} onClick={onScore}>
          Try again
        </Button>
      );
    }
  } else {
    body = idea.can_change
      ? "The AI's proposed scores are ready. Review each one, change what you disagree with, and confirm."
      : "The AI's proposed scores are ready for the idea's owner to review.";
    action = (
      <Link href={href!} className={buttonClass(idea.can_change ? "primary" : "secondary")}>
        {idea.can_change ? "Review the proposal" : "See the proposal"}
      </Link>
    );
  }

  return (
    <Card>
      <CardHeader
        title="Scoring"
        actions={latest ? <Badge tone={latest.status === "confirmed" ? "green" : "amber"}>{assessmentLabel(latest.status, latest.proposal_status)}</Badge> : null}
      />
      <div className="mt-3 text-sm text-neutral-600">{body}</div>
      {action && <div className="mt-4">{action}</div>}
    </Card>
  );
}
