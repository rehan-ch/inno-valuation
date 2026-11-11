"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";

import { useMe } from "@/components/app/me-context";
import { gapWords } from "@/components/compass/Compass";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Bar } from "@/components/ui/Bar";
import { buttonClass } from "@/components/ui/Button";
import { Card, CardDescription, CardHeader, CardTitle, Eyebrow, PageHeader } from "@/components/ui/Card";
import { Change } from "@/components/ui/Change";
import { Loading } from "@/components/ui/Loading";
import { ApiError } from "@/lib/api/client";
import { dimensionHref, getDimension } from "@/lib/api/insights";
import type { DimensionDetailOut, TrendPointOut } from "@/lib/api/types";
import { formatDate } from "@/lib/format";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string; notFound: boolean }
  | { kind: "ready"; detail: DimensionDetailOut };

/** One dimension: the book's description and fixed next steps as written, the
 * organisation's readiness score for it and the selected idea's score for it, kept apart,
 * each with its target, gap and earlier scores. Everything shown comes from the API. */
export function DimensionPage({ dimensionKey }: { dimensionKey: string }) {
  const { me } = useMe();
  const activeOrgId = me.active_organisation_id;
  const params = useSearchParams();
  const router = useRouter();
  const ideaId = params.get("idea");
  const [state, setState] = useState<State>({ kind: "loading" });
  const loadedFor = useRef(activeOrgId);

  useEffect(() => {
    let cancelled = false;
    // After a switch of organisation the idea in the address belongs to the other one:
    // show this organisation's own, and drop it from the address.
    const switched = loadedFor.current !== activeOrgId;
    loadedFor.current = activeOrgId;
    if (switched && ideaId) {
      router.replace(dimensionHref(dimensionKey));
      return;
    }
    setState({ kind: "loading" });
    getDimension(dimensionKey, ideaId)
      .then((detail) => {
        if (!cancelled) setState({ kind: "ready", detail });
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setState({
            kind: "error",
            message: err instanceof ApiError ? err.message : "Something went wrong.",
            notFound: err instanceof ApiError && err.status === 404,
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [dimensionKey, ideaId, activeOrgId, router]);

  if (state.kind === "loading") return <Loading>Loading the dimension...</Loading>;
  if (state.kind === "error") {
    return (
      <div className="space-y-4">
        <Alert tone="error">
          {state.notFound ? "This dimension or idea could not be found." : state.message}
        </Alert>
        <Link href="/dashboard" className={buttonClass("secondary", "sm")}>
          Back to the dashboard
        </Link>
      </div>
    );
  }

  const { detail } = state;
  const selected = detail.iq?.idea_id ?? ideaId;

  return (
    <div className="space-y-6">
      <PageHeader
        title={`${detail.order}. ${detail.name}`}
        description={detail.category.name}
        actions={
          <nav aria-label="Dimensions" className="flex flex-wrap items-center gap-2">
            {detail.previous && (
              <Link
                href={dimensionHref(detail.previous.key, selected)}
                className={buttonClass("secondary", "sm")}
              >
                <span aria-hidden="true">←</span> {detail.previous.name}
              </Link>
            )}
            {detail.next && (
              <Link
                href={dimensionHref(detail.next.key, selected)}
                className={buttonClass("secondary", "sm")}
              >
                {detail.next.name} <span aria-hidden="true">→</span>
              </Link>
            )}
            <Link href="/dashboard" className={buttonClass("ghost", "sm")}>
              Dashboard
            </Link>
          </nav>
        }
      />

      <Card>
        <CardTitle>About this dimension</CardTitle>
        <p className="mt-2 max-w-prose text-sm text-neutral-700">{detail.description}</p>
        {detail.sub_aspects.length > 0 && (
          <>
            <p className="mt-4 text-xs font-medium text-neutral-500">What it covers</p>
            <ul className="mt-2 flex flex-wrap gap-1.5">
              {detail.sub_aspects.map((aspect) => (
                <li key={aspect}>
                  <Badge dot={false}>{aspect}</Badge>
                </li>
              ))}
            </ul>
          </>
        )}
      </Card>

      <div
        className={`grid grid-cols-1 items-start gap-6${me.ai_enabled ? " lg:grid-cols-2" : ""}`}
      >
        <ReadinessSide detail={detail} />
        {me.ai_enabled && (
          <IqSide
            detail={detail}
            onSelectIdea={(id) => router.replace(dimensionHref(detail.key, id))}
          />
        )}
      </div>

      <Card>
        <CardTitle>Next steps from the method</CardTitle>
        <CardDescription>
          The fixed guidance for this dimension from the 12 Dimensions of Innovation, as written.
        </CardDescription>
        <p className="mt-3 max-w-prose border-l-2 border-primary pl-4 text-sm text-neutral-800">
          {detail.next_steps}
        </p>
      </Card>

      {me.ai_enabled && (
        <Card>
          <CardHeader
            title="AI advice"
            actions={<Badge dot={false}>Not available yet</Badge>}
          />
          <p className="mt-2 max-w-prose text-sm text-neutral-600">
            Advice written for your organisation on how to close the gap on {detail.name} will
            appear here. Until then, the next steps above are the method&apos;s own guidance.
          </p>
        </Card>
      )}
    </div>
  );
}

function TargetLine({ target, gap }: { target: number | null; gap: number | null }) {
  return (
    <p className="mt-3 text-sm text-neutral-600">
      {target === null ? (
        <>
          No target set.{" "}
          <Link href="/targets" className="font-medium text-primary hover:underline">
            Set a target
          </Link>
        </>
      ) : (
        <>
          Target <span className="font-medium text-neutral-900 tabular-nums">{target}</span>
          {gap !== null && <> · {gapWords(gap)}</>}
        </>
      )}
    </p>
  );
}

function Trend({ points, hrefFor }: { points: TrendPointOut[]; hrefFor: (id: string) => string }) {
  if (points.length < 2) return null;
  return (
    <div className="mt-5">
      <p className="text-xs font-medium text-neutral-500">Over time</p>
      <ul className="mt-2 divide-y divide-neutral-100 text-sm">
        {points.map((point) => (
          <li key={point.assessment_id} className="flex items-center justify-between gap-3 py-1.5">
            <Link href={hrefFor(point.assessment_id)} className="text-neutral-700 hover:text-primary hover:underline">
              {formatDate(point.at)}
            </Link>
            <span className="flex items-center gap-4">
              <Change change={point.change} direction={point.direction} />
              <span className="w-14 text-right tabular-nums">
                <span className="font-medium text-neutral-900">{point.score}</span>
                <span className="text-neutral-500"> / {point.maximum}</span>
              </span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ReadinessSide({ detail }: { detail: DimensionDetailOut }) {
  const readiness = detail.readiness;
  if (!readiness) {
    return (
      <Card>
        <CardTitle>Readiness</CardTitle>
        <CardDescription>
          The organisation has no final readiness result yet. Once the team&apos;s answers are
          agreed, this dimension&apos;s score out of 25 appears here.
        </CardDescription>
        <div className="mt-4">
          <Link href="/readiness" className={buttonClass("secondary", "sm")}>
            Readiness assessments
          </Link>
        </div>
      </Card>
    );
  }
  const labels = readiness.answer_scale.labels;
  return (
    <Card>
      <CardHeader
        title="Readiness"
        description="The whole organisation, from the team's agreed answers."
        actions={
          readiness.priority_rank !== null ? (
            <Badge tone="amber">Priority {readiness.priority_rank}</Badge>
          ) : null
        }
      />
      <div className="mt-4">
        <Eyebrow>Readiness score</Eyebrow>
        <p className="mt-1.5 text-3xl font-semibold text-neutral-900 tabular-nums">
          {readiness.score}
          <span className="ml-1 text-base font-normal text-neutral-500">/ {readiness.maximum}</span>
        </p>
        <Bar value={readiness.score} maximum={readiness.maximum} />
        <TargetLine target={readiness.target} gap={readiness.gap} />
      </div>

      <div className="mt-5">
        <p className="text-xs font-medium text-neutral-500">
          The agreed answers ({readiness.answer_scale.min} {labels[String(readiness.answer_scale.min)]}{" "}
          to {readiness.answer_scale.max} {labels[String(readiness.answer_scale.max)]})
        </p>
        <ol className="mt-2 divide-y divide-neutral-100 text-sm">
          {readiness.questions.map((question) => (
            <li key={question.id} className="flex items-start justify-between gap-4 py-2">
              <span className="text-neutral-700">{question.text}</span>
              <span className="shrink-0 font-medium text-neutral-900 tabular-nums">
                {question.answer ?? "–"}
                <span className="font-normal text-neutral-500"> / {readiness.answer_scale.max}</span>
              </span>
            </li>
          ))}
        </ol>
      </div>

      <Trend points={readiness.history} hrefFor={(id) => `/readiness/${id}/result`} />
      <p className="mt-4 text-xs text-neutral-500">
        <Link
          href={`/readiness/${readiness.assessment_id}/result`}
          className="font-medium text-primary hover:underline"
        >
          Result of {formatDate(readiness.finalised_at)}
        </Link>{" "}
        · question set version {readiness.question_set_version}
      </p>
    </Card>
  );
}

function IqSide({
  detail,
  onSelectIdea,
}: {
  detail: DimensionDetailOut;
  onSelectIdea: (ideaId: string) => void;
}) {
  const selectId = useId();
  const iq = detail.iq;
  if (!iq) {
    return (
      <Card>
        <CardTitle>Idea score</CardTitle>
        <CardDescription>
          No idea has confirmed scores yet. Once an idea&apos;s scores are confirmed, its score
          for this dimension out of 10 appears here.
        </CardDescription>
        <div className="mt-4">
          <Link href="/ideas" className={buttonClass("secondary", "sm")}>
            Ideas
          </Link>
        </div>
      </Card>
    );
  }
  return (
    <Card>
      <CardHeader
        title="Idea score"
        description={`"${iq.idea_title}", as confirmed by its owner.`}
        actions={
          <>
            {iq.priority_rank !== null && <Badge tone="amber">Priority {iq.priority_rank}</Badge>}
            {detail.ideas.length > 1 && (
              <>
                <label htmlFor={selectId} className="sr-only">
                  Idea
                </label>
                <select
                  id={selectId}
                  value={iq.idea_id}
                  onChange={(event) => onSelectIdea(event.target.value)}
                  className="h-8 max-w-44 rounded-md border border-neutral-300 bg-white px-2 text-[13px] text-neutral-900 shadow-xs focus:outline-2 focus:-outline-offset-1 focus:outline-primary"
                >
                  {detail.ideas.map((idea) => (
                    <option key={idea.idea_id} value={idea.idea_id}>
                      {idea.title}
                    </option>
                  ))}
                </select>
              </>
            )}
          </>
        }
      />
      <div className="mt-4">
        <Eyebrow>Score for this idea</Eyebrow>
        <p className="mt-1.5 text-3xl font-semibold text-neutral-900 tabular-nums">
          {iq.score}
          <span className="ml-1 text-base font-normal text-neutral-500">/ {iq.maximum}</span>
        </p>
        <Bar value={iq.score} maximum={iq.maximum} />
        <p className="mt-3 text-sm font-semibold text-neutral-900">{iq.level.name}</p>
        <p className="mt-0.5 text-sm text-neutral-600">{iq.level.text}</p>
        <TargetLine target={iq.target} gap={iq.gap} />
      </div>

      {iq.rationale.length > 0 && (
        <div className="mt-5 rounded-md border border-neutral-200 bg-neutral-50 px-3.5 py-3 text-sm">
          <p className="font-medium text-neutral-900">
            The AI proposed {iq.proposed_score}
            {iq.changed ? `; the owner set ${iq.score}` : "; the owner kept it"}
          </p>
          <ul className="mt-1.5 list-disc space-y-1 pl-4 text-neutral-700">
            {iq.rationale.map((sentence, i) => (
              // Keyed by position: the list is fixed and two sentences may be equal.
              <li key={i}>{sentence}</li>
            ))}
          </ul>
        </div>
      )}
      {iq.note && (
        <div className="mt-3 rounded-md border border-neutral-200 px-3.5 py-3 text-sm">
          <p className="font-medium text-neutral-900">Owner&apos;s note</p>
          <p className="mt-1 whitespace-pre-line text-neutral-700">{iq.note}</p>
        </div>
      )}

      <Trend
        points={iq.history}
        hrefFor={(id) => `/ideas/${iq.idea_id}/assessments/${id}`}
      />
      <p className="mt-4 text-xs text-neutral-500">
        <Link
          href={`/ideas/${iq.idea_id}/assessments/${iq.assessment_id}`}
          className="font-medium text-primary hover:underline"
        >
          Assessment of {formatDate(iq.confirmed_at)}
        </Link>{" "}
        · question set version {iq.question_set_version}
      </p>
    </Card>
  );
}
