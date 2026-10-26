"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardDescription, CardTitle, PageHeader } from "@/components/ui/Card";
import { Loading } from "@/components/ui/Loading";
import { ApiError } from "@/lib/api/client";
import {
  beginConsensus,
  getAssessment,
  getQuestionSet,
  saveMyAnswers,
  submitMyAnswers,
} from "@/lib/api/readiness";
import type { AssessmentOut, QuestionSetOut } from "@/lib/api/types";
import { useSubmit } from "@/lib/forms";

import { QuestionExplanation } from "./QuestionExplanation";
import { Bar, ScaleChoice, StickyBar } from "./ScaleChoice";
import { saveFailureMessage, STATUS_LABELS, STATUS_TONES } from "./status";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; assessment: AssessmentOut; questions: QuestionSetOut };

type SaveState = "idle" | "saving" | "saved" | "error";

/** One person's own 60 answers, saved as they go (spec 2.9), then submitted (spec 2.8).
 * The facilitator also sees everyone's progress here and starts agreeing the answers. */
export function QuestionnairePage({ assessmentId }: { assessmentId: string }) {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [save, setSave] = useState<SaveState>("idle");
  const [saveError, setSaveError] = useState<string | null>(null);
  // Questions whose last save failed. A later save that works does not clear them: each
  // stays marked until it is chosen again, so no answer is lost in silence.
  const [failed, setFailed] = useState<string[]>([]);
  // The submit lives here so the answers can lock while it runs.
  const submit = useSubmit();
  // Saves run one after another, so two quick clicks on one question land in order.
  // The chain never rejects: each save handles its own failure.
  const queue = useRef<Promise<unknown>>(Promise.resolve());
  const pending = useRef(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const assessment = await getAssessment(assessmentId);
        const questions = await getQuestionSet(assessment.question_set_version);
        if (!cancelled) {
          setAnswers(assessment.my_answers ?? {});
          setState({ kind: "ready", assessment, questions });
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
  }, [assessmentId]);

  if (state.kind === "loading") return <Loading>Loading the questions...</Loading>;
  if (state.kind === "error") return <Alert tone="error">{state.message}</Alert>;

  const { assessment, questions } = state;
  const editable =
    assessment.status === "collecting" && assessment.can_answer && !assessment.my_submitted_at;
  // A change made while the submit is in flight would be saved after it and rejected.
  const locked = !editable || submit.busy;
  const answered = Object.keys(answers).length;
  const total = assessment.question_count;

  function choose(questionId: string, value: number) {
    if (locked) return;
    const previous = answers[questionId];
    setAnswers((prev) => ({ ...prev, [questionId]: value }));
    setFailed((prev) => prev.filter((id) => id !== questionId));
    setSave("saving");
    pending.current += 1;
    queue.current = queue.current
      .then(() => saveMyAnswers(assessmentId, { [questionId]: value }))
      .then(
        (updated) => {
          pending.current -= 1;
          if (pending.current === 0) {
            setSave("saved");
            setState((prev) => (prev.kind === "ready" ? { ...prev, assessment: updated } : prev));
          }
        },
        (err: unknown) => {
          pending.current -= 1;
          setSave("error");
          setSaveError(saveFailureMessage(err));
          setFailed((prev) => (prev.includes(questionId) ? prev : [...prev, questionId]));
          // Show what the server holds, so the unsaved choice is not counted and choosing
          // it again is a real change that retries the save.
          setAnswers((prev) => {
            if (prev[questionId] !== value) return prev;
            const next = { ...prev };
            if (previous === undefined) delete next[questionId];
            else next[questionId] = previous;
            return next;
          });
        },
      );
  }

  const scale = Array.from(
    { length: questions.scale.max - questions.scale.min + 1 },
    (_, i) => questions.scale.min + i,
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Readiness questions"
        description="Answer each statement for your organisation as it is today: 1 means strongly disagree, 5 strongly agree."
        actions={
          <>
            <Badge tone={STATUS_TONES[assessment.status]}>{STATUS_LABELS[assessment.status]}</Badge>
            {assessment.status === "final" && (
              <Link
                href={`/readiness/${assessment.id}/result`}
                className="text-sm font-medium text-primary hover:underline"
              >
                See the result
              </Link>
            )}
          </>
        }
      />

      {assessment.my_submitted_at && (
        <Alert tone="success">
          Your answers are submitted. The facilitator will agree the team&apos;s answers next.
        </Alert>
      )}
      {assessment.my_answers === null && (
        <Alert tone="info">Your role watches the assessment; it does not answer.</Alert>
      )}
      {assessment.my_answers !== null &&
        !assessment.can_answer &&
        assessment.status === "collecting" && (
          <Alert tone="info">This organisation is archived, so your answers are read-only.</Alert>
        )}
      {assessment.can_answer && assessment.status !== "collecting" && !assessment.my_submitted_at && (
        <Alert tone="info">Answering is closed: the team&apos;s answers are being agreed.</Alert>
      )}

      {assessment.can_manage && assessment.status === "collecting" && (
        <FacilitatorPanel assessment={assessment} />
      )}

      {assessment.my_answers !== null && (
        <StickyBar>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <span className="text-sm font-medium text-neutral-900 tabular-nums">
              {answered} of {total} answered
            </span>
            <span
              role="status"
              aria-label="Save status"
              aria-live="polite"
              className={`text-xs ${save === "error" ? "text-red-700" : "text-neutral-500"}`}
            >
              {save === "saving" && "Saving..."}
              {save === "saved" && failed.length === 0 && "Saved"}
              {save === "saved" &&
                failed.length > 0 &&
                `Saved, but ${unsavedCount(failed.length)}. Choose again where marked.`}
              {save === "error" && saveError}
            </span>
            {editable && (
              <SubmitControl
                submit={submit}
                ready={answered === total}
                waitForSaves={() => queue.current}
                onSubmitted={(updated) =>
                  setState((prev) =>
                    prev.kind === "ready" ? { ...prev, assessment: updated } : prev,
                  )
                }
                assessmentId={assessmentId}
              />
            )}
          </div>
          <Bar value={answered} maximum={total} tone="accent" />
          <nav aria-label="Dimensions" className="mt-3 flex flex-wrap gap-1.5">
            {questions.dimensions.map((d) => {
              const done = d.questions.filter((q) => q.id in answers).length;
              return (
                <a
                  key={d.key}
                  href={`#${d.key}`}
                  className={`rounded-md border px-2 py-0.5 text-xs tabular-nums transition-colors ${
                    done === d.questions.length
                      ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                      : "border-neutral-200 bg-white text-neutral-600 hover:border-neutral-300 hover:text-neutral-900"
                  }`}
                >
                  {d.name} {done}/{d.questions.length}
                </a>
              );
            })}
          </nav>
        </StickyBar>
      )}

      {questions.dimensions.map((dimension) => (
        <section
          key={dimension.key}
          id={dimension.key}
          aria-labelledby={`${dimension.key}-title`}
          className="scroll-mt-52 rounded-lg border border-neutral-200 bg-white"
        >
          <div className="border-b border-neutral-200 px-5 py-4">
            <h2 id={`${dimension.key}-title`} className="text-sm font-semibold text-neutral-900">
              <span className="mr-2 text-neutral-400 tabular-nums">{dimension.order}.</span>
              {dimension.name}
            </h2>
            <p className="mt-1 text-sm text-neutral-600">{dimension.description}</p>
          </div>
          <ol className="divide-y divide-neutral-100">
            {dimension.questions.map((question) => (
              <li key={question.id} className="px-5 py-4">
                <fieldset disabled={locked}>
                  <legend className="text-sm text-neutral-900">{question.text}</legend>
                  {failed.includes(question.id) && (
                    <p className="mt-1 text-xs font-medium text-red-700">
                      Not saved. Choose your answer again.
                    </p>
                  )}
                  <div className="mt-2.5 flex flex-wrap items-center gap-3">
                    <span className="hidden w-28 text-right text-xs text-neutral-500 sm:inline">
                      {questions.scale.labels[String(questions.scale.min)]}
                    </span>
                    <ScaleChoice
                      name={question.id}
                      scale={scale}
                      value={answers[question.id]}
                      onChange={(value) => choose(question.id, value)}
                      ariaLabel={(value) => {
                        const label = questions.scale.labels[String(value)];
                        return label ? `${value}, ${label}` : String(value);
                      }}
                    />
                    <span className="hidden text-xs text-neutral-500 sm:inline">
                      {questions.scale.labels[String(questions.scale.max)]}
                    </span>
                  </div>
                </fieldset>
                {/* Outside the fieldset, so it still works once answers are locked. */}
                {assessment.can_answer && (
                  <QuestionExplanation questionId={question.id} version={questions.version} />
                )}
              </li>
            ))}
          </ol>
        </section>
      ))}
    </div>
  );
}

function unsavedCount(n: number): string {
  return n === 1 ? "1 answer was not saved" : `${n} answers were not saved`;
}

function SubmitControl({
  submit,
  ready,
  assessmentId,
  waitForSaves,
  onSubmitted,
}: {
  submit: ReturnType<typeof useSubmit>;
  ready: boolean;
  assessmentId: string;
  waitForSaves: () => Promise<unknown>;
  onSubmitted: (assessment: AssessmentOut) => void;
}) {
  const { busy, error, run } = submit;
  const [confirming, setConfirming] = useState(false);

  async function handleSubmit() {
    // The last answer may still be saving; submit only once every save has landed.
    const updated = await run(async () => {
      await waitForSaves();
      return submitMyAnswers(assessmentId);
    });
    if (updated) onSubmitted(updated);
  }

  return (
    <span className="ml-auto flex flex-wrap items-center gap-2">
      {error && <span className="text-xs text-red-700">{error.message}</span>}
      {!confirming ? (
        <Button disabled={!ready} onClick={() => setConfirming(true)}>
          Submit my answers
        </Button>
      ) : (
        <>
          <span className="text-xs text-neutral-600">You cannot change them afterwards.</span>
          <Button busy={busy} onClick={() => void handleSubmit()}>
            Submit now
          </Button>
          <Button variant="secondary" disabled={busy} onClick={() => setConfirming(false)}>
            Not yet
          </Button>
        </>
      )}
    </span>
  );
}

function FacilitatorPanel({ assessment }: { assessment: AssessmentOut }) {
  const router = useRouter();
  const { busy, error, run } = useSubmit();
  const [confirming, setConfirming] = useState(false);
  const participants = assessment.participants ?? [];

  async function handleBegin() {
    const begun = await run(() => beginConsensus(assessment.id));
    if (begun) router.push(`/readiness/${assessment.id}/consensus`);
  }

  return (
    <Card>
      <CardTitle>Team progress</CardTitle>
      <CardDescription>
        When enough people have submitted, start agreeing the answers. Answering closes for
        everyone, and anyone who has not submitted is left out.
      </CardDescription>
      {participants.length === 0 ? (
        <p className="mt-3 text-sm text-neutral-600">Nobody has started answering yet.</p>
      ) : (
        <ul className="mt-3 divide-y divide-neutral-100">
          {participants.map((p) => (
            <li key={p.user_id} className="flex items-center justify-between gap-3 py-2 text-sm">
              <span className="text-neutral-900">{p.name}</span>
              {p.submitted_at ? (
                <Badge tone="green">Submitted</Badge>
              ) : (
                <span className="text-neutral-500 tabular-nums">
                  {p.answered} of {assessment.question_count} answered
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      {error && (
        <div className="mt-3">
          <Alert tone="error">{error.message}</Alert>
        </div>
      )}
      <div className="mt-4 flex flex-wrap items-center gap-2">
        {!confirming ? (
          <Button
            variant="secondary"
            disabled={assessment.submitted_count === 0}
            onClick={() => setConfirming(true)}
          >
            Start agreeing answers
          </Button>
        ) : (
          <>
            <span className="text-sm text-neutral-600">
              Close answering with {assessment.submitted_count} submitted?
            </span>
            <Button busy={busy} onClick={() => void handleBegin()}>
              Yes, start agreeing
            </Button>
            <Button variant="secondary" disabled={busy} onClick={() => setConfirming(false)}>
              Cancel
            </Button>
          </>
        )}
      </div>
    </Card>
  );
}
