"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Card, CardTitle, PageHeader } from "@/components/ui/Card";
import { Loading } from "@/components/ui/Loading";
import { ApiError } from "@/lib/api/client";
import { getResult } from "@/lib/api/readiness";
import type { ResultOut } from "@/lib/api/types";
import { formatDate } from "@/lib/format";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; result: ResultOut };

/** A final readiness result, every number straight from the API (the engine's output).
 * The band text and the next steps are the book's words, shown as written (spec 2.4, 8). */
export function ResultPage({ assessmentId }: { assessmentId: string }) {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    getResult(assessmentId)
      .then((result) => {
        if (!cancelled) setState({ kind: "ready", result });
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
  }, [assessmentId]);

  if (state.kind === "loading") return <Loading>Loading the result...</Loading>;
  if (state.kind === "error") return <Alert tone="error">{state.message}</Alert>;

  const { result } = state;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Readiness result"
        description={`Final on ${formatDate(result.finalised_at)} · answers from ${result.submitted_count} ${
          result.submitted_count === 1 ? "person" : "people"
        } · question set version ${result.question_set_version}`}
      />

      <section
        aria-label="Total"
        className="rounded-2xl border border-neutral-200 border-t-4 border-t-accent bg-white p-6 shadow-sm"
      >
        <p className="text-xs font-medium tracking-wide text-neutral-500 uppercase">
          Readiness score
        </p>
        <p className="mt-1 font-serif text-5xl font-semibold text-neutral-900">
          {result.total}
          <span className="ml-1 text-2xl text-neutral-500">/ {result.total_maximum}</span>
        </p>
        <p className="mt-4 text-lg font-semibold text-primary">{result.band.name}</p>
        <p className="mt-1 text-sm text-neutral-700">{result.band.text}</p>
      </section>

      <section aria-label="Categories" className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {result.categories.map((category) => (
          <div
            key={category.key}
            className="rounded-2xl border border-neutral-200 bg-white p-4 shadow-sm"
          >
            <p className="text-sm font-medium text-neutral-900">{category.name}</p>
            <p className="mt-1 font-serif text-2xl font-semibold text-neutral-900">
              {category.score}
              <span className="ml-1 text-base text-neutral-500">/ {category.maximum}</span>
            </p>
            <Bar value={category.score} maximum={category.maximum} />
          </div>
        ))}
      </section>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardTitle>Focus first</CardTitle>
          <p className="mt-1 text-sm text-neutral-600">
            The lowest-scoring dimensions, with the next steps from the method.
          </p>
          <ol className="mt-4 space-y-4">
            {result.priorities.map((priority) => (
              <li key={priority.key} className="flex gap-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-white">
                  {priority.rank}
                </span>
                <span>
                  <span className="block text-sm font-medium text-neutral-900">
                    {priority.name}{" "}
                    <span className="font-normal text-neutral-500">
                      {priority.score} / {priority.maximum}
                    </span>
                  </span>
                  <span className="mt-0.5 block text-sm text-neutral-600">
                    {priority.next_steps}
                  </span>
                </span>
              </li>
            ))}
          </ol>
        </Card>

        <Card>
          <CardTitle>Strengths</CardTitle>
          <p className="mt-1 text-sm text-neutral-600">
            {result.strengths.length > 0
              ? "The dimensions that score above every priority."
              : "No dimension scores above the priorities yet, so none stands out as a strength."}
          </p>
          <ul className="mt-4 space-y-3">
            {result.strengths.map((strength) => (
              <li key={strength.key}>
                <span className="flex items-baseline justify-between gap-3 text-sm">
                  <span className="font-medium text-neutral-900">{strength.name}</span>
                  <span className="text-neutral-500">
                    {strength.score} / {strength.maximum}
                  </span>
                </span>
                <Bar value={strength.score} maximum={strength.maximum} />
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card>
        <CardTitle>The 12 dimensions</CardTitle>
        <ul className="mt-4 grid grid-cols-1 gap-x-8 gap-y-4 md:grid-cols-2">
          {result.dimensions.map((dimension) => (
            <li key={dimension.key}>
              <span className="flex items-baseline justify-between gap-3 text-sm">
                <span className="text-neutral-900">
                  {dimension.order}. {dimension.name}
                </span>
                <span className="font-medium text-neutral-900">
                  {dimension.score}
                  <span className="font-normal text-neutral-500"> / {dimension.maximum}</span>
                </span>
              </span>
              <Bar value={dimension.score} maximum={dimension.maximum} />
            </li>
          ))}
        </ul>
      </Card>

      <p className="text-sm">
        <Link href="/readiness" className="underline">
          Back to assessments
        </Link>
      </p>
    </div>
  );
}

function Bar({ value, maximum }: { value: number; maximum: number }) {
  return (
    <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-neutral-100" aria-hidden="true">
      <div
        className="h-full rounded-full bg-primary"
        style={{ width: `${Math.round((value / maximum) * 100)}%` }}
      />
    </div>
  );
}
