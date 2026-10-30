"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Bar } from "@/components/ui/Bar";
import { Card, CardDescription, CardTitle, Eyebrow, PageHeader } from "@/components/ui/Card";
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
        actions={
          <Link href="/readiness" className="text-sm font-medium text-primary hover:underline">
            All assessments
          </Link>
        }
      />

      <section
        aria-label="Total"
        className="grid grid-cols-1 gap-6 rounded-lg border border-neutral-200 bg-white p-6 md:grid-cols-[auto_1fr] md:gap-10"
      >
        <div>
          <Eyebrow>Readiness score</Eyebrow>
          <p className="mt-2 text-5xl font-semibold tracking-tight text-neutral-900 tabular-nums">
            {result.total}
            <span className="ml-1.5 text-2xl font-normal text-neutral-500">/ {result.total_maximum}</span>
          </p>
        </div>
        <div className="border-neutral-200 md:border-l md:pl-10">
          <Eyebrow>Band</Eyebrow>
          <p className="mt-2 text-lg font-semibold text-neutral-900">{result.band.name}</p>
          <p className="mt-1 max-w-prose text-sm text-neutral-600">{result.band.text}</p>
        </div>
      </section>

      <section
        aria-label="Categories"
        className="grid grid-cols-1 gap-px overflow-hidden rounded-lg border border-neutral-200 bg-neutral-200 md:grid-cols-3"
      >
        {result.categories.map((category) => (
          <div key={category.key} className="bg-white p-5">
            <p className="text-sm font-medium text-neutral-900">{category.name}</p>
            <p className="mt-1 text-2xl font-semibold text-neutral-900 tabular-nums">
              {category.score}
              <span className="ml-1 text-sm font-normal text-neutral-500">/ {category.maximum}</span>
            </p>
            <Bar value={category.score} maximum={category.maximum} />
          </div>
        ))}
      </section>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardTitle>Focus first</CardTitle>
          <CardDescription>
            The lowest-scoring dimensions, with the next steps from the method.
          </CardDescription>
          <ol className="mt-4 divide-y divide-neutral-100">
            {result.priorities.map((priority) => (
              <li key={priority.key} className="flex gap-3 py-3 first:pt-0 last:pb-0">
                <span className="w-5 shrink-0 text-sm font-semibold text-neutral-400 tabular-nums">
                  {priority.rank}
                </span>
                <span className="min-w-0">
                  <span className="flex items-baseline justify-between gap-3 text-sm">
                    <span className="font-medium text-neutral-900">{priority.name}</span>
                    <span className="shrink-0 text-neutral-500 tabular-nums">
                      {priority.score} / {priority.maximum}
                    </span>
                  </span>
                  <span className="mt-0.5 block text-sm text-neutral-600">{priority.next_steps}</span>
                </span>
              </li>
            ))}
          </ol>
        </Card>

        <Card>
          <CardTitle>Strengths</CardTitle>
          <CardDescription>
            {result.strengths.length > 0
              ? "The dimensions that score above every priority."
              : "No dimension scores above the priorities yet, so none stands out as a strength."}
          </CardDescription>
          <ul className="mt-4 space-y-4">
            {result.strengths.map((strength) => (
              <li key={strength.key}>
                <span className="flex items-baseline justify-between gap-3 text-sm">
                  <span className="font-medium text-neutral-900">{strength.name}</span>
                  <span className="text-neutral-500 tabular-nums">
                    {strength.score} / {strength.maximum}
                  </span>
                </span>
                <Bar value={strength.score} maximum={strength.maximum} tone="accent" />
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card>
        <CardTitle>The 12 dimensions</CardTitle>
        <ul className="mt-4 grid grid-cols-1 gap-x-10 gap-y-4 md:grid-cols-2">
          {result.dimensions.map((dimension) => (
            <li key={dimension.key}>
              <span className="flex items-baseline justify-between gap-3 text-sm">
                <span className="text-neutral-900">
                  <span className="mr-2 text-neutral-400 tabular-nums">{dimension.order}.</span>
                  {dimension.name}
                </span>
                <span className="font-medium text-neutral-900 tabular-nums">
                  {dimension.score}
                  <span className="font-normal text-neutral-500"> / {dimension.maximum}</span>
                </span>
              </span>
              <Bar value={dimension.score} maximum={dimension.maximum} />
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
