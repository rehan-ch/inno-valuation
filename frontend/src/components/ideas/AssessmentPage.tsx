"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

import { ScaleChoice } from "@/components/readiness/ScaleChoice";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Bar } from "@/components/ui/Bar";
import { Button, buttonClass } from "@/components/ui/Button";
import { Card, CardDescription, CardTitle, Eyebrow, PageHeader } from "@/components/ui/Card";
import { TextAreaField } from "@/components/ui/fields";
import { Loading } from "@/components/ui/Loading";
import { StickyBar, stickyScrollMargin } from "@/components/ui/StickyBar";
import { ApiError } from "@/lib/api/client";
import { confirmAssessment, getAssessment, requestAssessment, saveReview } from "@/lib/api/ideas";
import type { DimensionReviewOut, IqAssessmentOut } from "@/lib/api/types";
import { formatDate, formatDateTime } from "@/lib/format";
import { useSubmit } from "@/lib/forms";
import { formatMoney } from "@/lib/money";

import { saveFailureMessage } from "@/components/readiness/status";

/** How often the page asks whether a pending proposal is ready, and for how long. */
export const POLL_MS = 2500;
const MAX_WAIT_MS = 6 * 60_000;

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; assessment: IqAssessmentOut; slow: boolean };

/** One IQ assessment of an idea: the AI's proposal while it is made, the owner's review,
 * and the confirmed result. Every number on the result comes from the engine. */
export function AssessmentPage({ ideaId, assessmentId }: { ideaId: string; assessmentId: string }) {
  const router = useRouter();
  const [state, setState] = useState<State>({ kind: "loading" });
  const again = useSubmit();

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const startedAt = Date.now();
    async function load() {
      try {
        const assessment = await getAssessment(ideaId, assessmentId);
        if (cancelled) return;
        const pending = assessment.status === "proposed" && assessment.proposal_status === "pending";
        setState({ kind: "ready", assessment, slow: pending && Date.now() - startedAt > MAX_WAIT_MS });
        if (pending) timer = setTimeout(() => void load(), POLL_MS);
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
      if (timer) clearTimeout(timer);
    };
  }, [ideaId, assessmentId]);

  if (state.kind === "loading") return <Loading>Loading the assessment...</Loading>;
  if (state.kind === "error") return <Alert tone="error">{state.message}</Alert>;

  const { assessment } = state;

  async function scoreAgain() {
    const next = await again.run(() => requestAssessment(ideaId));
    if (next) router.push(`/ideas/${ideaId}/assessments/${next.id}`);
  }

  const header = (
    <PageHeader
      title={assessment.status === "confirmed" ? "Innovation Quotient" : "Proposed scores"}
      description={
        <>
          <Link href={`/ideas/${ideaId}`} className="font-medium text-primary hover:underline">
            {assessment.idea_title}
          </Link>
          {" · "}
          {assessment.status === "confirmed" && assessment.confirmed_at
            ? `confirmed ${formatDate(assessment.confirmed_at)}${
                assessment.confirmed_by_name ? ` by ${assessment.confirmed_by_name}` : ""
              }`
            : `requested ${formatDateTime(assessment.requested_at)}${
                assessment.requested_by_name ? ` by ${assessment.requested_by_name}` : ""
              }`}
          {" · "}question set version {assessment.question_set_version}
        </>
      }
      actions={
        <Badge tone={assessment.status === "confirmed" ? "green" : "amber"}>
          {assessment.status === "confirmed"
            ? "Confirmed"
            : assessment.status === "superseded"
              ? "Replaced"
              : assessment.proposal_status === "pending"
                ? "AI is proposing"
                : assessment.proposal_status === "failed"
                  ? "Proposal failed"
                  : "Proposed by AI"}
        </Badge>
      }
    />
  );

  if (assessment.status === "confirmed") {
    return (
      <div className="space-y-6">
        {header}
        <ResultView assessment={assessment} />
      </div>
    );
  }

  if (assessment.status === "superseded") {
    return (
      <div className="space-y-6">
        {header}
        <Alert tone="info">
          A newer proposal replaced this one before it was confirmed.{" "}
          <Link href={`/ideas/${ideaId}`} className="font-medium text-primary hover:underline">
            Back to the idea
          </Link>
        </Alert>
      </div>
    );
  }

  if (assessment.proposal_status === "pending") {
    return (
      <div className="space-y-6">
        {header}
        <Card>
          <Loading>The AI is reading the idea and proposing a score for each dimension...</Loading>
          <p className="mt-3 text-sm text-neutral-600">
            {state.slow
              ? "This is taking longer than usual. You can leave this page; the proposal will be here when it is ready."
              : "This usually takes a minute or two. The page updates by itself."}
          </p>
        </Card>
      </div>
    );
  }

  if (assessment.proposal_status === "failed") {
    return (
      <div className="space-y-6">
        {header}
        <Alert tone="error">The proposal could not be made this time. Nothing was scored.</Alert>
        {again.error && <Alert tone="error">{again.error.message}</Alert>}
        {assessment.can_review && (
          <Button busy={again.busy} onClick={() => void scoreAgain()}>
            Try again
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {header}
      {assessment.sample && <SampleNotice />}
      {assessment.can_review ? (
        <ReviewView
          ideaId={ideaId}
          assessment={assessment}
          onChange={(next) => setState({ kind: "ready", assessment: next, slow: false })}
        />
      ) : (
        <>
          <Alert tone="info">
            The idea&apos;s owner, or an owner or admin, reviews and confirms these scores.
          </Alert>
          <ProposalList assessment={assessment} />
        </>
      )}
    </div>
  );
}

function SampleNotice() {
  return (
    <Alert tone="info">
      Sample scores: the AI is not connected yet, so every dimension shows the middle of the
      scale with placeholder reasons. The review and the arithmetic work as they will with the
      real proposal.
    </Alert>
  );
}

function confidenceLabel(value: string | null): string {
  if (value === null) return "";
  const percent = Math.round(Number(value) * 100);
  return `${percent}% sure`;
}

function Rationale({ dimension }: { dimension: DimensionReviewOut }) {
  return (
    <div className="rounded-md border border-neutral-200 bg-neutral-50 px-3.5 py-3 text-sm">
      <p className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="font-medium text-neutral-900">
          Proposed by AI: {dimension.proposed_score ?? "–"}
        </span>
        {dimension.proposed_confidence !== null && (
          <span className="text-xs text-neutral-500">{confidenceLabel(dimension.proposed_confidence)}</span>
        )}
      </p>
      {dimension.proposed_rationale && (
        <p className="mt-1.5 text-neutral-700">{dimension.proposed_rationale.join(" ")}</p>
      )}
    </div>
  );
}

function ProposalList({ assessment }: { assessment: IqAssessmentOut }) {
  return (
    <Card>
      <CardTitle>The 12 dimensions</CardTitle>
      <ol className="mt-4 divide-y divide-neutral-100">
        {assessment.dimensions.map((d) => (
          <li key={d.key} className="py-4 first:pt-0 last:pb-0">
            <p className="text-sm font-semibold text-neutral-900">
              <span className="mr-2 text-neutral-400 tabular-nums">{d.order}.</span>
              {d.name}
            </p>
            <div className="mt-2">
              <Rationale dimension={d} />
            </div>
          </li>
        ))}
      </ol>
    </Card>
  );
}

type SaveState = "idle" | "saving" | "saved" | "error";

/** The owner's review: every dimension shows the AI's score and reasons, a 1 to 10 control
 * for the final score, and a note. Changes save as they are made; Confirm makes them final. */
function ReviewView({
  ideaId,
  assessment,
  onChange,
}: {
  ideaId: string;
  assessment: IqAssessmentOut;
  onChange: (next: IqAssessmentOut) => void;
}) {
  const [finals, setFinals] = useState<Record<string, number | null>>(() =>
    Object.fromEntries(assessment.dimensions.map((d) => [d.key, d.final_score])),
  );
  const [notes, setNotes] = useState<Record<string, string>>(() =>
    Object.fromEntries(assessment.dimensions.map((d) => [d.key, d.note ?? ""])),
  );
  const [save, setSave] = useState<SaveState>("idle");
  const [saveError, setSaveError] = useState<string | null>(null);
  const confirm = useSubmit();
  const [confirming, setConfirming] = useState(false);
  // Saves run one after another, so two quick changes land in order. Never rejects.
  const queue = useRef<Promise<unknown>>(Promise.resolve());
  const pending = useRef(0);

  const scale = Array.from(
    { length: assessment.scale.max - assessment.scale.min + 1 },
    (_, i) => assessment.scale.min + i,
  );
  const proposed = Object.fromEntries(assessment.dimensions.map((d) => [d.key, d.proposed_score]));
  const changed = assessment.dimensions.filter(
    (d) => finals[d.key] !== null && finals[d.key] !== d.proposed_score,
  ).length;

  function enqueue(review: { scores?: Record<string, number | null>; notes?: Record<string, string | null> }) {
    setSave("saving");
    pending.current += 1;
    queue.current = queue.current
      .then(() => saveReview(ideaId, assessment.id, { scores: review.scores ?? {}, notes: review.notes ?? {} }))
      .then(
        (updated) => {
          pending.current -= 1;
          if (pending.current === 0) {
            setSave("saved");
            onChange(updated);
          }
        },
        (err: unknown) => {
          pending.current -= 1;
          setSave("error");
          setSaveError(saveFailureMessage(err));
        },
      );
  }

  function choose(key: string, value: number) {
    // Choosing the proposed score puts the proposal back (null), so nothing counts as changed.
    const next = value === proposed[key] ? null : value;
    setFinals((prev) => ({ ...prev, [key]: next }));
    enqueue({ scores: { [key]: next } });
  }

  function saveNote(key: string) {
    const text = notes[key] ?? "";
    const stored = assessment.dimensions.find((d) => d.key === key)?.note ?? "";
    if (text.trim() === stored) return;
    enqueue({ notes: { [key]: text.trim() || null } });
  }

  async function handleConfirm() {
    const result = await confirm.run(async () => {
      await queue.current;
      return confirmAssessment(ideaId, assessment.id);
    });
    if (result) onChange(result);
  }

  return (
    <>
      <StickyBar>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <span className="text-sm font-medium text-neutral-900 tabular-nums">
            {changed === 0 ? "No scores changed" : `${changed} of 12 scores changed`}
          </span>
          <span
            role="status"
            aria-label="Save status"
            aria-live="polite"
            className={`text-xs ${save === "error" ? "text-red-700" : "text-neutral-500"}`}
          >
            {save === "saving" && "Saving..."}
            {save === "saved" && "Saved"}
            {save === "error" && saveError}
          </span>
          <span className="ml-auto flex flex-wrap items-center gap-2">
            {confirm.error && <span className="text-xs text-red-700">{confirm.error.message}</span>}
            {!confirming ? (
              <Button disabled={confirm.busy} onClick={() => setConfirming(true)}>
                Confirm the scores
              </Button>
            ) : (
              <>
                <span className="text-xs text-neutral-600">
                  The IQ is worked out from these scores and cannot change afterwards.
                </span>
                <Button busy={confirm.busy} onClick={() => void handleConfirm()}>
                  Confirm now
                </Button>
                <Button variant="secondary" disabled={confirm.busy} onClick={() => setConfirming(false)}>
                  Not yet
                </Button>
              </>
            )}
          </span>
        </div>
      </StickyBar>

      {assessment.missing_information.length > 0 && (
        <Card>
          <CardTitle>What the AI could not tell from the idea</CardTitle>
          <CardDescription>
            Answering these in the idea&apos;s description and scoring again would make the
            proposal more certain.
          </CardDescription>
          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-neutral-700">
            {assessment.missing_information.map((q) => (
              <li key={q}>{q}</li>
            ))}
          </ul>
        </Card>
      )}

      <p className="text-sm text-neutral-600">
        For each dimension, read the AI&apos;s reasons and choose the score you stand behind. The
        proposed score is selected until you change it. Levels: 1 to 3 Continuous Improvement, 4
        to 6 Innovation, 7 to 10 Invention.
      </p>

      {assessment.dimensions.map((d) => {
        const current = finals[d.key] ?? d.proposed_score;
        const isChanged = finals[d.key] !== null && finals[d.key] !== d.proposed_score;
        return (
          <section
            key={d.key}
            id={d.key}
            aria-labelledby={`${d.key}-title`}
            className={`${stickyScrollMargin} rounded-lg border border-neutral-200 bg-white p-5`}
          >
            <h2 id={`${d.key}-title`} className="text-sm font-semibold text-neutral-900">
              <span className="mr-2 text-neutral-400 tabular-nums">{d.order}.</span>
              {d.name}
            </h2>
            <p className="mt-1 text-sm text-neutral-600">{d.description}</p>
            <div className="mt-3">
              <Rationale dimension={d} />
            </div>
            <fieldset className="mt-4" disabled={confirm.busy}>
              <legend className="text-[13px] font-medium text-neutral-800">
                Your score
                {isChanged && (
                  <span className="ml-2 font-normal text-amber-800">
                    changed from {d.proposed_score}
                  </span>
                )}
              </legend>
              <div className="mt-2 flex flex-wrap items-center gap-3">
                <ScaleChoice
                  name={`${d.key}-score`}
                  scale={scale}
                  value={current}
                  onChange={(value) => choose(d.key, value)}
                  ariaLabel={(value) => `${d.name}: ${value}`}
                />
                {current !== null && <span className="text-xs text-neutral-500">{levelOf(assessment, current)}</span>}
              </div>
            </fieldset>
            <div className="mt-3">
              <TextAreaField
                label="Your note"
                hint="Optional. Why you kept or changed the score."
                rows={2}
                value={notes[d.key] ?? ""}
                onChange={(e) => setNotes((prev) => ({ ...prev, [d.key]: e.target.value }))}
                onBlur={() => saveNote(d.key)}
                disabled={confirm.busy}
              />
            </div>
          </section>
        );
      })}
    </>
  );
}

function levelOf(assessment: IqAssessmentOut, score: number): string {
  return assessment.levels.find((l) => l.min <= score && score <= l.max)?.name ?? "";
}

/** The confirmed assessment, every number straight from the engine (spec 3, 5, 7). */
function ResultView({ assessment }: { assessment: IqAssessmentOut }) {
  const iq = Number(assessment.iq);
  const maximum = Number(assessment.iq_maximum);
  const vfm = assessment.vfm;
  return (
    <>
      {assessment.sample && <SampleNotice />}
      <section
        aria-label="Innovation Quotient"
        className="grid grid-cols-1 gap-6 rounded-lg border border-neutral-200 bg-white p-6 md:grid-cols-[auto_1fr] md:gap-10"
      >
        <div>
          <Eyebrow>Innovation Quotient</Eyebrow>
          <p className="mt-2 text-5xl font-semibold tracking-tight text-neutral-900 tabular-nums">
            {assessment.iq}
            <span className="ml-1.5 text-2xl font-normal text-neutral-500">/ {assessment.iq_maximum}</span>
          </p>
          <Bar value={iq} maximum={maximum} />
        </div>
        <div className="border-neutral-200 md:border-l md:pl-10">
          <Eyebrow>Value for money</Eyebrow>
          {vfm?.per_point ? (
            <>
              <p className="mt-2 text-lg font-semibold text-neutral-900 tabular-nums">
                {formatMoney(vfm.per_point, vfm.currency)}
                <span className="ml-1 text-sm font-normal text-neutral-500">per innovation point</span>
              </p>
              <p className="mt-1 text-sm text-neutral-600">
                {vfm.investment ? `${formatMoney(vfm.investment, vfm.currency)} planned investment` : ""}
                {" divided by the IQ. Lower is better."}
              </p>
            </>
          ) : (
            <>
              <p className="mt-2 text-lg font-semibold text-neutral-900">Not calculable</p>
              <p className="mt-1 text-sm text-neutral-600">{vfm?.not_calculable_reason}</p>
            </>
          )}
        </div>
      </section>

      <section
        aria-label="Categories"
        className="grid grid-cols-1 gap-px overflow-hidden rounded-lg border border-neutral-200 bg-neutral-200 md:grid-cols-3"
      >
        {assessment.categories.map((category) => (
          <div key={category.key} className="bg-white p-5">
            <p className="text-sm font-medium text-neutral-900">{category.name}</p>
            <p className="mt-1 text-2xl font-semibold text-neutral-900 tabular-nums">
              {category.score ?? "–"}
              <span className="ml-1 text-sm font-normal text-neutral-500">/ {category.maximum}</span>
            </p>
            {category.score !== null && <Bar value={Number(category.score)} maximum={Number(category.maximum)} />}
          </div>
        ))}
      </section>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardTitle>Focus first</CardTitle>
          <CardDescription>The lowest-scoring dimensions, with the next steps from the method.</CardDescription>
          <ol className="mt-4 divide-y divide-neutral-100">
            {assessment.priorities.map((p) => (
              <li key={p.key} className="flex gap-3 py-3 first:pt-0 last:pb-0">
                <span className="w-5 shrink-0 text-sm font-semibold text-neutral-400 tabular-nums">{p.rank}</span>
                <span className="min-w-0">
                  <span className="flex items-baseline justify-between gap-3 text-sm">
                    <span className="font-medium text-neutral-900">{p.name}</span>
                    <span className="shrink-0 text-neutral-500 tabular-nums">
                      {p.score} / {assessment.scale.max} · {p.level_name}
                    </span>
                  </span>
                  <span className="mt-0.5 block text-sm text-neutral-600">{p.next_steps}</span>
                </span>
              </li>
            ))}
          </ol>
        </Card>
        <Card>
          <CardTitle>How the scores were set</CardTitle>
          <CardDescription>
            The AI proposed each score; the idea&apos;s owner confirmed or changed it (both are
            kept). The IQ is the sum of the 12 final scores out of 120, as a percentage.
          </CardDescription>
          <dl className="mt-4 grid grid-cols-2 gap-4 text-sm">
            <Stat label="Scores changed" value={assessment.dimensions.filter((d) => d.changed).length} />
            <Stat label="Scores kept" value={assessment.dimensions.filter((d) => !d.changed).length} />
            {assessment.confirmed_by_name && <Stat label="Confirmed by" value={assessment.confirmed_by_name} />}
            {assessment.confirmed_at && <Stat label="Confirmed on" value={formatDate(assessment.confirmed_at)} />}
          </dl>
        </Card>
      </div>

      <Card>
        <CardTitle>The 12 dimensions</CardTitle>
        <ol className="mt-4 divide-y divide-neutral-100">
          {assessment.dimensions.map((d) => (
            <li key={d.key} className="py-4 first:pt-0 last:pb-0">
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                <p className="text-sm font-semibold text-neutral-900">
                  <span className="mr-2 text-neutral-400 tabular-nums">{d.order}.</span>
                  {d.name}
                </p>
                <p className="text-sm tabular-nums">
                  <span className="font-semibold text-neutral-900">{d.final_score ?? d.proposed_score}</span>
                  <span className="text-neutral-500"> / {assessment.scale.max}</span>
                  {d.level && <span className="ml-2 text-neutral-600">{d.level.name}</span>}
                  {d.changed && (
                    <span className="ml-2 text-xs text-amber-800">changed from {d.proposed_score}</span>
                  )}
                </p>
              </div>
              <Bar value={d.final_score ?? d.proposed_score ?? 0} maximum={assessment.scale.max} />
              <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
                <Rationale dimension={d} />
                {d.note && (
                  <div className="rounded-md border border-neutral-200 px-3.5 py-3 text-sm">
                    <p className="font-medium text-neutral-900">Owner&apos;s note</p>
                    <p className="mt-1 whitespace-pre-line text-neutral-700">{d.note}</p>
                  </div>
                )}
              </div>
            </li>
          ))}
        </ol>
      </Card>

      <p className="text-xs text-neutral-500">
        <Link href={`/ideas/${assessment.idea_id}`} className={buttonClass("ghost", "sm")}>
          Back to the idea
        </Link>
      </p>
    </>
  );
}

function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-neutral-500">{label}</dt>
      <dd className="mt-0.5 font-medium text-neutral-900 tabular-nums">{value}</dd>
    </div>
  );
}
