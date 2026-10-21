"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useMe } from "@/components/app/me-context";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardTitle, PageHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Loading } from "@/components/ui/Loading";
import { ApiError } from "@/lib/api/client";
import { assessmentHref, listAssessments, startAssessment } from "@/lib/api/readiness";
import type { AssessmentSummaryOut } from "@/lib/api/types";
import { formatDate } from "@/lib/format";
import { useSubmit } from "@/lib/forms";
import { activeMembership, canManage } from "@/lib/roles";

import { MY_STATUS_LABELS, STATUS_LABELS, STATUS_TONES } from "./status";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; assessments: AssessmentSummaryOut[] };

/** The organisation's readiness assessments: start one, answer, agree, see results. */
export function ReadinessListPage() {
  const { me } = useMe();
  const router = useRouter();
  const activeOrgId = me.active_organisation_id;
  const membership = activeMembership(me);
  const manage =
    membership !== null &&
    canManage(membership.role) &&
    membership.organisation_status === "active";
  const [state, setState] = useState<State>({ kind: "loading" });
  const { busy, error, run } = useSubmit();

  useEffect(() => {
    if (!activeOrgId) return;
    let cancelled = false;
    listAssessments()
      .then((assessments) => {
        if (!cancelled) setState({ kind: "ready", assessments });
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
  }, [activeOrgId]);

  async function handleStart() {
    const started = await run(() => startAssessment());
    if (started) router.push(`/readiness/${started.id}`);
  }

  const header = (
    <PageHeader
      title="Readiness assessment"
      description="Your team answers 60 questions across the 12 Dimensions of Innovation, agrees its answers, and gets a score out of 300."
    />
  );

  if (!activeOrgId) {
    return (
      <div className="space-y-4">
        {header}
        <Alert tone="info">Choose an organisation in the switcher above.</Alert>
      </div>
    );
  }
  if (state.kind === "loading") return <Loading>Loading assessments...</Loading>;
  if (state.kind === "error") return <Alert tone="error">{state.message}</Alert>;

  const { assessments } = state;
  const open = assessments.find((a) => a.status !== "final");

  return (
    <div className="space-y-6">
      {header}
      {error && <Alert tone="error">{error.message}</Alert>}
      {manage && !open && (
        <Card>
          <CardTitle>Start an assessment</CardTitle>
          <p className="mt-1 text-sm text-neutral-600">
            Everyone on the team answers on their own. When enough answers are in, you agree the
            team&apos;s answer to each question and finalise the result.
          </p>
          <div className="mt-4">
            <Button busy={busy} onClick={() => void handleStart()}>
              Start a readiness assessment
            </Button>
          </div>
        </Card>
      )}
      <Card>
        <CardTitle>Assessments</CardTitle>
        {assessments.length === 0 ? (
          <div className="mt-4">
            <EmptyState title="No assessment yet.">
              {manage
                ? "Start one above to invite your team's answers."
                : "An owner or admin starts the assessment; you will find it here."}
            </EmptyState>
          </div>
        ) : (
          <ul className="mt-2 divide-y divide-neutral-200">
            {assessments.map((a) => (
              <li key={a.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 py-3 text-sm">
                <span className="min-w-0">
                  <span className="block font-medium text-neutral-900">
                    Started {formatDate(a.started_at ?? a.created_at)}
                    {a.created_by_name ? ` by ${a.created_by_name}` : ""}
                  </span>
                  <span className="block text-neutral-600">
                    {a.status === "final" && a.total !== null
                      ? `${a.total} out of 300 · ${a.band_name ?? ""}`
                      : a.my_status
                        ? MY_STATUS_LABELS[a.my_status]
                        : `${a.submitted_count} submitted so far`}
                  </span>
                </span>
                <Badge tone={STATUS_TONES[a.status]}>{STATUS_LABELS[a.status]}</Badge>
                <Link
                  href={assessmentHref(a, manage)}
                  className="ml-auto text-sm font-medium text-primary hover:underline"
                >
                  {a.status === "final"
                    ? "See the result"
                    : a.status === "consensus" && manage
                      ? "Agree the answers"
                      : a.my_status && a.my_status !== "submitted" && a.status === "collecting"
                        ? "Answer the questions"
                        : "Open"}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
