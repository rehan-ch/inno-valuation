
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Check,
  CheckCheck,
  ChevronRight,
  CircleAlert,
  ClipboardCheck,
  Cloud,
  CloudCheck,
  Compass,
  LayoutGrid,
  ListChecks,
  LockKeyhole,
  Save,
  Sparkles,
  Target,
  UsersRound,
} from "lucide-react";

import { useMe } from "@/components/app/me-context";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
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
import { saveFailureMessage, STATUS_LABELS, STATUS_TONES } from "./status";

import "./questionnaire.css";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | {
    kind: "ready";
    assessment: AssessmentOut;
    questions: QuestionSetOut;
  };

type SaveState = "idle" | "saving" | "saved" | "error";

export function QuestionnairePage({
  assessmentId,
}: {
  assessmentId: string;
}) {
  const { me } = useMe();
  const [state, setState] = useState<State>({ kind: "loading" });
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [save, setSave] = useState<SaveState>("idle");
  const [currentIndex, setCurrentIndex] = useState(0);
  const [reviewMode, setReviewMode] = useState(false);
  const [mobileDimensions, setMobileDimensions] = useState(false);

  const queue = useRef<Promise<unknown>>(Promise.resolve());
  const pending = useRef(0);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [failed, setFailed] = useState<string[]>([]);
  const failedRef = useRef(new Set<string>());
  // Counts every failed save, so a submit can tell whether one failed while it waited.
  const failures = useRef(0);
  const submit = useSubmit();

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const assessment = await getAssessment(assessmentId);
        const questions = await getQuestionSet(
          assessment.question_set_version,
        );

        if (!cancelled) {
          setAnswers(assessment.my_answers ?? {});
          setState({ kind: "ready", assessment, questions });
        }
      } catch (err) {
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
  }, [assessmentId]);

  if (state.kind === "loading") {
    return <Loading>Loading your innovation assessment...</Loading>;
  }

  if (state.kind === "error") {
    return <Alert tone="error">{state.message}</Alert>;
  }

  const { assessment, questions } = state;

  const editable =
    assessment.status === "collecting" &&
    assessment.can_answer &&
    !assessment.my_submitted_at;

  const locked = !editable || submit.busy;

  const items = questions.dimensions.flatMap((dimension) =>
    dimension.questions.map((question) => ({
      dimension,
      question,
    })),
  );

  const total = items.length;
  const answered = items.filter(
    ({ question }) => answers[question.id] !== undefined,
  ).length;

  const percentage =
    total > 0 ? Math.round((answered / total) * 100) : 0;

  const safeIndex = Math.min(
    Math.max(0, currentIndex),
    Math.max(0, total - 1),
  );

  const current = items[safeIndex];
  const remaining = total - answered;
  const allAnswered = total > 0 && remaining === 0;

  const scale = Array.from(
    { length: questions.scale.max - questions.scale.min + 1 },
    (_, index) => questions.scale.min + index,
  );

  // A failed save puts back what the server holds, so the answers shown are the ones
  // saved and a marked question does not block the submit. (Blocking would strand anyone
  // who wants the answer it went back to: choosing a checked radio again does nothing.)
  const canSubmit = allAnswered && !submit.busy;

  function navigate(index: number) {
    if (index < 0 || index >= total) return;

    setCurrentIndex(index);
    setReviewMode(false);
    setMobileDimensions(false);
  }

  function choose(questionId: string, value: number) {
    if (locked) return;

    const previousValue = answers[questionId];

    if (
      previousValue === value &&
      !failedRef.current.has(questionId)
    ) return;

    setAnswers((previous) => ({
      ...previous,
      [questionId]: value,
    }));

    setSave("saving");
    pending.current += 1;

    queue.current = queue.current
      .then(() =>
        saveMyAnswers(assessmentId, { [questionId]: value }),
      )
      .then(
        (updated) => {
          pending.current -= 1;

          failedRef.current.delete(questionId);
          setFailed(Array.from(failedRef.current));

          if (pending.current === 0) {
            setSave("saved");

            setState((previous) =>
              previous.kind === "ready"
                ? { ...previous, assessment: updated }
                : previous,
            );
          }
        },
        (err: unknown) => {
          pending.current -= 1;
          failures.current += 1;

          failedRef.current.add(questionId);
          setFailed(Array.from(failedRef.current));
          setSaveError(saveFailureMessage(err));
          setSave("error");

          setAnswers((previous) => {
            if (previous[questionId] !== value) return previous;

            const next = { ...previous };

            if (previousValue === undefined) {
              delete next[questionId];
            } else {
              next[questionId] = previousValue;
            }

            return next;
          });
        },
      );
  }

  async function waitForSaves() {
    const failuresBefore = failures.current;
    await queue.current;

    // A save that failed while the submit waited changed an answer the person has not
    // seen yet: stop, so they can look at it before the answers are locked.
    if (failures.current > failuresBefore) {
      throw new ApiError(
        "answers_not_saved",
        "Some answers were not saved. Choose the marked answers again.",
        0,
      );
    }
  }

  function openReview() {
    setReviewMode(true);
    setMobileDimensions(false);
  }

  const firstUnanswered = items.findIndex(
    ({ question }) => answers[question.id] === undefined,
  );

  return (
    <div className="iv-q">
      <div className="iv-q-topline">
        <Link href="/readiness" className="iv-q-back">
          <ArrowLeft size={16} />
          All assessments
        </Link>

        <Badge tone={STATUS_TONES[assessment.status]}>
          {STATUS_LABELS[assessment.status]}
        </Badge>
      </div>

      <section className="iv-q-hero">
        <div className="iv-q-hero-content">
          <div className="iv-q-eyebrow">
            <span className="iv-q-gold-dot" />
            INNOVATION INTELLIGENCE ASSESSMENT
          </div>

          <h1>Discover your innovation potential.</h1>

          <p>
            Evaluate where your organisation stands today.
            Navigate the 12 dimensions, reflect on each statement,
            and build a clearer picture of your readiness.
          </p>

          <div className="iv-q-hero-tags">
            <span>
              <LayoutGrid size={15} />
              {questions.dimensions.length} dimensions
            </span>
            <span>
              <ClipboardCheck size={15} />
              {total} questions
            </span>
            <span>
              <CloudCheck size={15} />
              {editable ? "Autosave enabled" : "Read-only"}
            </span>
          </div>
        </div>

        <div className="iv-q-hero-art" aria-hidden="true">
          <div className="iv-q-orbit iv-q-orbit-one" />
          <div className="iv-q-orbit iv-q-orbit-two" />
          <div className="iv-q-orbit iv-q-orbit-three" />
          <Compass size={78} strokeWidth={1.1} />
        </div>
      </section>

      {assessment.my_submitted_at && (
        <Alert tone="success">
          Your answers are submitted. The facilitator will agree
          the team&apos;s answers next.
        </Alert>
      )}

      {assessment.my_answers === null && (
        <Alert tone="info">
          Your role watches the assessment; it does not answer.
        </Alert>
      )}

      {assessment.my_answers !== null &&
        !assessment.can_answer &&
        assessment.status === "collecting" && (
          <Alert tone="info">
            This organisation is archived, so your answers are read-only.
          </Alert>
        )}

      {assessment.can_answer &&
        assessment.status !== "collecting" &&
        !assessment.my_submitted_at && (
          <Alert tone="info">
            Answering is closed: the team&apos;s answers are being agreed.
          </Alert>
        )}

      {assessment.can_manage &&
        assessment.status === "collecting" && (
          <FacilitatorPanel assessment={assessment} />
        )}

      <section className="iv-q-progress">
        <div className="iv-q-progress-heading">
          <div>
            <span className="iv-q-section-kicker">
              YOUR ASSESSMENT PROGRESS
            </span>
            <h2>
              {allAnswered
                ? "All questions answered"
                : "Keep your momentum"}
            </h2>
            <p>
              {answered} of {total} questions answered
              {remaining > 0
                ? ` · ${remaining} remaining`
                : " · Ready for review"}
            </p>
          </div>

          <div
            className="iv-q-progress-ring"
            style={{
              background: `conic-gradient(#E4B963 ${percentage}%, #DFE5EF ${percentage}%)`,
            }}
            aria-label={`${percentage}% complete`}
          >
            <div>
              <strong>{percentage}%</strong>
              <span>complete</span>
            </div>
          </div>
        </div>

        <div
          className="iv-q-progress-track"
          role="progressbar"
          aria-label="Assessment completion"
          aria-valuenow={answered}
          aria-valuemin={0}
          aria-valuemax={total}
        >
          <div style={{ width: `${percentage}%` }} />
        </div>

        <div className="iv-q-progress-footer">
          <span
            role="status"
            aria-label="Save status"
            aria-live="polite"
            className={
              save === "error"
                ? "iv-q-save-state iv-q-save-error"
                : "iv-q-save-state"
            }
          >

            {save === "saving" ? (
              <>
                <Cloud size={15} aria-hidden="true" />
                Saving your answer...
              </>
            ) : save === "saved" ? (
              <>
                <CloudCheck size={15} aria-hidden="true" />

                {failed.length === 0
                  ? "Saved"
                  : `Saved, but ${failed.length} ${failed.length === 1
                    ? "answer was not saved"
                    : "answers were not saved"
                  }. Choose again where marked.`}
              </>
            ) : save === "error" ? (
              <>
                <CircleAlert size={15} aria-hidden="true" />
                {saveError ?? "Some answers were not saved."}
              </>
            ) : (
              <>
                <Save size={15} aria-hidden="true" />
                Progress is saved as you answer
              </>
            )}

          </span>

          {assessment.my_answers !== null && (
            <button
              type="button"
              className="iv-q-review-link"
              onClick={() =>
                reviewMode ? setReviewMode(false) : openReview()
              }
            >
              {reviewMode ? (
                <>
                  <BookOpen size={16} /> Focused view
                </>
              ) : (
                <>
                  <ListChecks size={16} /> Review all answers
                </>
              )}
            </button>
          )}
        </div>
      </section>

      {reviewMode ? (
        <section className="iv-q-review">
          <div className="iv-q-review-heading">
            <span className="iv-q-section-kicker">
              COMPLETE ASSESSMENT
            </span>
            <h2>Review your responses</h2>
            <p>
              Check every dimension before submitting your answers.
              Select any question to revisit it.
            </p>

            {firstUnanswered >= 0 && (
              <button
                type="button"
                className="iv-q-outline-button"
                onClick={() => navigate(firstUnanswered)}
              >
                <Target size={16} />
                Go to first unanswered question
              </button>
            )}
          </div>

          <div className="iv-q-review-grid">
            {questions.dimensions.map((dimension) => {
              const dimensionItems = items
                .map((item, index) => ({ ...item, index }))
                .filter(
                  (item) => item.dimension.key === dimension.key,
                );

              const done = dimensionItems.filter(
                ({ question }) =>
                  answers[question.id] !== undefined,
              ).length;

              return (
                <div className="iv-q-review-card" key={dimension.key}>
                  <div className="iv-q-review-card-head">
                    <div>
                      <span>
                        DIMENSION{" "}
                        {String(dimension.order).padStart(2, "0")}
                      </span>
                      <h3>{dimension.name}</h3>
                    </div>

                    <span
                      className={
                        done === dimensionItems.length
                          ? "iv-q-count iv-q-count-done"
                          : "iv-q-count"
                      }
                    >
                      {done}/{dimensionItems.length}
                    </span>
                  </div>

                  <div className="iv-q-review-questions">
                    {dimensionItems.map(
                      ({ question, index }, questionIndex) => {
                        const answer = answers[question.id];
                        const isAnswered = answer !== undefined;

                        return (
                          <button
                            key={question.id}
                            type="button"
                            className="iv-q-review-item"
                            onClick={() => navigate(index)}
                          >
                            <span className="iv-q-review-number">
                              {questionIndex + 1}
                            </span>

                            <span className="iv-q-review-text">
                              {question.text}
                            </span>

                            <span
                              className={
                                isAnswered
                                  ? "iv-q-answer-chip"
                                  : "iv-q-answer-chip iv-q-unanswered"
                              }
                            >
                              {failed.includes(question.id) ? "Not saved" : isAnswered ? answer : "—"}
                            </span>

                            <ChevronRight size={15} />
                          </button>
                        );
                      },
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {editable && (
            <div className="iv-q-review-submit">
              <div>
                <h3>
                  {allAnswered
                    ? "Ready to submit?"
                    : "Almost there."}
                </h3>
                <p>
                  {allAnswered
                    ? "Review your answers carefully. You cannot change them after submission."
                    : `Complete the remaining ${remaining} questions before submitting.`}
                </p>
              </div>

              <SubmitControl
                submit={submit}
                ready={canSubmit}
                assessmentId={assessmentId}
                waitForSaves={waitForSaves}
                onSubmitted={(updated) =>
                  setState((previous) =>
                    previous.kind === "ready"
                      ? { ...previous, assessment: updated }
                      : previous,
                  )
                }
              />
            </div>
          )}
        </section>
      ) : current ? (
        <div className="iv-q-workspace">
          <aside className="iv-q-sidebar">
            <div className="iv-q-sidebar-title">
              <div className="iv-q-sidebar-icon">
                <LayoutGrid size={18} />
              </div>
              <div>
                <h2>Innovation dimensions</h2>
                <p>Explore your assessment</p>
              </div>
            </div>

            <button
              type="button"
              className="iv-q-mobile-dimension-toggle"
              aria-expanded={mobileDimensions}
              onClick={() =>
                setMobileDimensions((previous) => !previous)
              }
            >
              <span>
                {current.dimension.name}
              </span>
              <span>
                {mobileDimensions ? "Hide" : "Change"}
              </span>
            </button>

            <nav
              aria-label="Assessment dimensions"
              className={`iv-q-dimension-list ${mobileDimensions ? "iv-q-dimensions-open" : ""
                }`}
            >
              {questions.dimensions.map((dimension) => {
                const dimensionItems = items
                  .map((item, index) => ({ ...item, index }))
                  .filter(
                    (item) =>
                      item.dimension.key === dimension.key,
                  );

                const done = dimensionItems.filter(
                  ({ question }) =>
                    answers[question.id] !== undefined,
                ).length;

                const active =
                  current.dimension.key === dimension.key;

                return (
                  <button
                    key={dimension.key}
                    type="button"
                    onClick={() =>
                      navigate(dimensionItems[0]?.index ?? 0)
                    }
                    aria-current={active ? "step" : undefined}
                    className={`iv-q-dimension ${active ? "iv-q-dimension-active" : ""
                      }`}
                  >
                    <span className="iv-q-dimension-number">
                      {done === dimensionItems.length ? (
                        <Check size={15} />
                      ) : (
                        String(dimension.order).padStart(2, "0")
                      )}
                    </span>

                    <span className="iv-q-dimension-name">
                      {dimension.name}
                      <small>
                        {done} of {dimensionItems.length} answered
                      </small>
                    </span>

                    <ChevronRight size={16} />
                  </button>
                );
              })}
            </nav>

            <div className="iv-q-sidebar-bottom">
              <Sparkles size={18} />
              <p>
                Every answer helps build a clearer picture of
                your organisation&apos;s innovation readiness.
              </p>
            </div>
          </aside>

          <section className="iv-q-question-panel">
            <div className="iv-q-question-top">
              <div className="iv-q-question-breadcrumb">
                <span>
                  DIMENSION{" "}
                  {String(current.dimension.order).padStart(2, "0")}
                </span>
                <ChevronRight size={14} />
                <span>
                  QUESTION {safeIndex + 1} OF {total}
                </span>
              </div>

              <span className="iv-q-question-status">
                {answers[current.question.id] !== undefined ? (
                  <>
                    <CheckCheck size={15} />
                    Answered
                  </>
                ) : (
                  <>Not answered</>
                )}
              </span>
            </div>

            <div className="iv-q-question-body">
              <div className="iv-q-question-category">
                <Target size={17} />
                {current.dimension.name}
              </div>

              <h2>{current.question.text}</h2>

              {failed.includes(current.question.id) && (
                <p className="mt-2 text-sm font-medium text-red-700">
                  Not saved. Choose your answer again.
                </p>
              )}
              <p className="iv-q-question-context">
                {current.dimension.description}
              </p>

              <div className="iv-q-answer-section">
                <div className="iv-q-answer-title">
                  <span>YOUR ASSESSMENT</span>
                  <span>Select one answer</span>
                </div>

                <fieldset
                  disabled={locked}
                  className="iv-q-rating-fieldset"
                >
                  <legend className="sr-only">
                    {current.question.text}
                  </legend>

                  <div className="iv-q-rating-grid">
                    {scale.map((value) => {
                      const selected =
                        answers[current.question.id] === value;

                      const label =
                        questions.scale.labels[String(value)];

                      return (
                        <label
                          key={value}
                          className={`iv-q-rating ${selected ? "iv-q-rating-selected" : ""
                            }`}
                        >
                          <input
                            className="sr-only"
                            type="radio"
                            name={current.question.id}
                            value={value}
                            checked={selected}
                            onChange={() =>
                              choose(current.question.id, value)
                            }
                            aria-label={label ? `${value}, ${label}` : String(value)}
                            title={label || undefined}
                          />

                          <span className="iv-q-rating-value">
                            {value}
                          </span>
                          {selected && (
                            <Check size={15} aria-hidden="true" />
                          )}
                        </label>
                      );
                    })}
                  </div>

                  <div className="iv-q-rating-labels">
                    <span>
                      {
                        questions.scale.labels[
                        String(questions.scale.min)
                        ]
                      }
                    </span>
                    <span>
                      {
                        questions.scale.labels[
                        String(questions.scale.max)
                        ]
                      }
                    </span>
                  </div>
                </fieldset>
              </div>

              {assessment.can_answer && me.ai_enabled && (
                <div className="iv-q-ai-section">
                  <div className="iv-q-ai-heading">
                    <Sparkles size={19} />
                    <div>
                      <strong>Need a little clarity?</strong>
                      <span>
                        Understand the question before answering.
                      </span>
                    </div>
                  </div>

                  <QuestionExplanation
                    key={current.question.id}
                    questionId={current.question.id}
                    version={questions.version}
                  />
                </div>
              )}
            </div>

            <div className="iv-q-question-footer">
              <button
                type="button"
                className="iv-q-outline-button"
                disabled={safeIndex === 0}
                onClick={() => navigate(safeIndex - 1)}
              >
                <ArrowLeft size={17} />
                Previous
              </button>

              <span className="iv-q-footer-position">
                {safeIndex + 1} / {total}
              </span>

              {safeIndex === total - 1 ? (
                <button
                  type="button"
                  className="iv-q-primary-button"
                  onClick={openReview}
                >
                  Review answers
                  <ListChecks size={17} />
                </button>
              ) : (
                <button
                  type="button"
                  className="iv-q-primary-button"
                  onClick={() => navigate(safeIndex + 1)}
                >
                  Next question
                  <ArrowRight size={17} />
                </button>
              )}
            </div>
          </section>
        </div>
      ) : (
        <Alert tone="info">
          No questions are available in this assessment.
        </Alert>
      )}

      {!reviewMode && editable && allAnswered && (
        <div className="iv-q-ready-banner">
          <div>
            <CheckCheck size={20} />
            <span>
              All questions answered. Your assessment is ready
              for review.
            </span>
          </div>

          <button type="button" onClick={openReview}>
            Review responses
            <ArrowRight size={17} />
          </button>
        </div>
      )}

      {assessment.status === "final" && (
        <Link
          href={`/readiness/${assessment.id}/result`}
          className="iv-q-primary-button iv-q-result-link"
        >
          See the result
          <ArrowRight size={17} />
        </Link>
      )}
    </div>
  );
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
    const updated = await run(async () => {
      await waitForSaves();
      return submitMyAnswers(assessmentId);
    });

    if (updated) onSubmitted(updated);
  }

  return (
    <div className="iv-q-submit-control">
      {error && <Alert tone="error">{error.message}</Alert>}

      {!confirming ? (
        <Button
          disabled={!ready}
          onClick={() => setConfirming(true)}
        >
          Submit my answers
        </Button>
      ) : (
        <div className="iv-q-confirmation">
          <p>
            <LockKeyhole size={16} />
            You cannot change your answers afterwards.
          </p>

          <Button
            busy={busy}
            onClick={() => void handleSubmit()}
          >
            Submit now
          </Button>

          <Button
            variant="secondary"
            disabled={busy}
            onClick={() => setConfirming(false)}
          >
            Not yet
          </Button>
        </div>
      )}
    </div>
  );
}

function FacilitatorPanel({
  assessment,
}: {
  assessment: AssessmentOut;
}) {
  const router = useRouter();
  const { busy, error, run } = useSubmit();
  const [confirming, setConfirming] = useState(false);
  const participants = assessment.participants ?? [];

  async function handleBegin() {
    const begun = await run(() =>
      beginConsensus(assessment.id),
    );

    if (begun) {
      router.push(`/readiness/${assessment.id}/consensus`);
    }
  }

  return (
    <section className="iv-q-facilitator">
      <div className="iv-q-facilitator-heading">
        <div className="iv-q-facilitator-icon">
          <UsersRound size={20} />
        </div>

        <div>
          <span className="iv-q-section-kicker">
            FACILITATOR WORKSPACE
          </span>
          <h2>Team progress</h2>
          <p>
            Monitor individual submissions before moving to
            team consensus.
          </p>
        </div>

        <span className="iv-q-facilitator-count">
          {assessment.submitted_count} submitted
        </span>
      </div>

      <p className="iv-q-facilitator-note">
        When enough people have submitted, start agreeing the
        answers. Answering closes for everyone, and anyone who
        has not submitted is left out.
      </p>

      {participants.length === 0 ? (
        <div className="iv-q-empty-team">
          Nobody has started answering yet.
        </div>
      ) : (
        <div className="iv-q-participants">
          {participants.map((participant) => (
            <div
              key={participant.user_id}
              className="iv-q-participant"
            >
              <div className="iv-q-participant-avatar">
                {participant.name.charAt(0).toUpperCase()}
              </div>

              <strong>{participant.name}</strong>

              {participant.submitted_at ? (
                <Badge tone="green">Submitted</Badge>
              ) : (
                <span>
                  {participant.answered} of{" "}
                  {assessment.question_count} answered
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      {error && <Alert tone="error">{error.message}</Alert>}

      <div className="iv-q-facilitator-actions">
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
            <span>
              Close answering with{" "}
              {assessment.submitted_count} submitted?
            </span>

            <Button
              busy={busy}
              onClick={() => void handleBegin()}
            >
              Yes, start agreeing
            </Button>

            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => setConfirming(false)}
            >
              Cancel
            </Button>
          </>
        )}
      </div>
    </section>
  );
}
