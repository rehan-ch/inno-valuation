"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/Card";
import { Loading } from "@/components/ui/Loading";
import { ApiError } from "@/lib/api/client";
import {
  finaliseAssessment,
  getAssessment,
  getConsensus,
  getQuestionSet,
  saveConsensus,
} from "@/lib/api/readiness";
import type { ConsensusOut, QuestionConsensusOut, QuestionSetOut } from "@/lib/api/types";
import { useSubmit } from "@/lib/forms";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; consensus: ConsensusOut; questions: QuestionSetOut };

type SaveState = "idle" | "saving" | "saved" | "error";

/** The facilitator agrees the team's answer to each question (Amy Q5): everyone's
 * answers, the mean and the spread are shown; the result uses the agreed answers only. */
export function ConsensusPage({ assessmentId }: { assessmentId: string }) {
  const router = useRouter();
  const [state, setState] = useState<State>({ kind: "loading" });
  const [save, setSave] = useState<SaveState>("idle");
  const queue = useRef<Promise<unknown>>(Promise.resolve());

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const assessment = await getAssessment(assessmentId);
        if (assessment.status === "final") {
          router.replace(`/readiness/${assessmentId}/result`);
          return;
        }
        const [consensus, questions] = await Promise.all([
          getConsensus(assessmentId),
          getQuestionSet(assessment.question_set_version),
        ]);
        if (!cancelled) setState({ kind: "ready", consensus, questions });
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
  }, [assessmentId, router]);

  if (state.kind === "loading") return <Loading>Loading everyone&apos;s answers...</Loading>;
  if (state.kind === "error") return <Alert tone="error">{state.message}</Alert>;

  const { consensus, questions } = state;
  const byQuestion = new Map(consensus.questions.map((q) => [q.question_id, q]));

  function persist(changes: Parameters<typeof saveConsensus>[1]) {
    setSave("saving");
    queue.current = queue.current
      .then(() => saveConsensus(assessmentId, changes))
      .then(
        (updated) => {
          setSave("saved");
          setState((prev) => (prev.kind === "ready" ? { ...prev, consensus: updated } : prev));
        },
        () => setSave("error"),
      );
  }

  function agree(questionId: string, value: number) {
    setState((prev) =>
      prev.kind === "ready"
        ? {
            ...prev,
            consensus: {
              ...prev.consensus,
              questions: prev.consensus.questions.map((q) =>
                q.question_id === questionId ? { ...q, agreed: value } : q,
              ),
            },
          }
        : prev,
    );
    persist({ answers: { [questionId]: value } });
  }

  const agreedCount = consensus.questions.filter((q) => q.agreed !== null).length;
  const scale = Array.from(
    { length: questions.scale.max - questions.scale.min + 1 },
    (_, i) => questions.scale.min + i,
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Agree the team's answers"
        description="For each question, see what everyone answered and set the answer the team agrees on. The result uses the agreed answers only."
      />
      <Alert tone="info">
        {consensus.participants.length === 1
          ? `Answers from ${consensus.participants[0]}.`
          : `Answers from ${consensus.participants.length} people: ${consensus.participants.join(", ")}.`}{" "}
        Questions where answers are far apart are marked for discussion.
      </Alert>

      <div className="sticky top-(--app-header-h) z-10 rounded-2xl border border-neutral-200 bg-white/90 p-4 shadow-sm backdrop-blur">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <span className="text-sm font-medium text-neutral-900">
            {agreedCount} of {consensus.question_count} agreed
          </span>
          <span
            role="status"
            aria-live="polite"
            className={`text-xs ${save === "error" ? "text-red-700" : "text-neutral-500"}`}
          >
            {save === "saving" && "Saving..."}
            {save === "saved" && "Saved"}
            {save === "error" && "Not saved. Check your connection and choose again."}
          </span>
          <FinaliseControl
            assessmentId={assessmentId}
            ready={agreedCount === consensus.question_count}
            onFinalised={() => router.push(`/readiness/${assessmentId}/result`)}
          />
        </div>
        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-neutral-100" aria-hidden="true">
          <div
            className="h-full rounded-full bg-accent transition-all"
            style={{ width: `${(agreedCount / consensus.question_count) * 100}%` }}
          />
        </div>
      </div>

      {questions.dimensions.map((dimension) => (
        <section
          key={dimension.key}
          aria-labelledby={`${dimension.key}-title`}
          className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm"
        >
          <h2 id={`${dimension.key}-title`} className="text-base font-semibold text-neutral-900">
            {dimension.order}. {dimension.name}
          </h2>
          <ol className="mt-4 space-y-6">
            {dimension.questions.map((question) => {
              const row = byQuestion.get(question.id);
              if (!row) return null;
              return (
                <ConsensusRow
                  key={question.id}
                  text={question.text}
                  row={row}
                  scale={scale}
                  onAgree={(value) => agree(question.id, value)}
                  onNote={(note) => persist({ notes: { [question.id]: note || null } })}
                />
              );
            })}
          </ol>
        </section>
      ))}
      <p className="text-sm">
        <Link href="/readiness" className="underline">
          Back to assessments
        </Link>
      </p>
    </div>
  );
}

function ConsensusRow({
  text,
  row,
  scale,
  onAgree,
  onNote,
}: {
  text: string;
  row: QuestionConsensusOut;
  scale: number[];
  onAgree: (value: number) => void;
  onNote: (note: string) => void;
}) {
  const [note, setNote] = useState(row.note ?? "");

  return (
    <li className={row.wide_spread ? "rounded-xl border-l-4 border-amber-400 pl-4" : undefined}>
      <fieldset>
        <legend className="text-sm text-neutral-900">{text}</legend>
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-neutral-600">
          <span>
            {row.answers.map((a) => (
              <span key={a.name} className="mr-3 whitespace-nowrap">
                {a.name}: <strong className="text-neutral-900">{a.answer}</strong>
              </span>
            ))}
          </span>
          {row.mean !== null && (
            <span>
              Average <strong className="text-neutral-900">{row.mean}</strong>
            </span>
          )}
          {row.spread !== null && (
            <span>
              Spread <strong className="text-neutral-900">{row.spread}</strong>
            </span>
          )}
          {row.wide_spread && <Badge tone="amber">Discuss: answers differ</Badge>}
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium text-neutral-700">Agreed answer</span>
          {scale.map((value) => {
            const chosen = row.agreed === value;
            return (
              <label
                key={value}
                className={`flex h-9 w-9 cursor-pointer items-center justify-center rounded-full border text-sm font-medium transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-primary ${
                  chosen
                    ? "border-primary bg-primary text-white"
                    : "border-neutral-300 bg-white text-neutral-700 hover:border-primary"
                }`}
              >
                <input
                  type="radio"
                  name={`agreed-${row.question_id}`}
                  value={value}
                  checked={chosen}
                  onChange={() => onAgree(value)}
                  aria-label={`Agreed answer ${value}`}
                  className="sr-only"
                />
                {value}
              </label>
            );
          })}
        </div>
      </fieldset>
      <label className="mt-3 block">
        <span className="sr-only">Note for this question</span>
        <input
          type="text"
          value={note}
          maxLength={2000}
          placeholder="Optional note: why the team agreed this"
          onChange={(e) => setNote(e.target.value)}
          onBlur={() => {
            if (note.trim() !== (row.note ?? "")) onNote(note.trim());
          }}
          className="block w-full rounded-lg border border-neutral-200 bg-white px-3 py-1.5 text-xs text-neutral-900 placeholder:text-neutral-400 focus:outline-2 focus:-outline-offset-1 focus:outline-accent"
        />
      </label>
    </li>
  );
}

function FinaliseControl({
  assessmentId,
  ready,
  onFinalised,
}: {
  assessmentId: string;
  ready: boolean;
  onFinalised: () => void;
}) {
  const { busy, error, run } = useSubmit();
  const [confirming, setConfirming] = useState(false);

  async function handleFinalise() {
    const result = await run(() => finaliseAssessment(assessmentId));
    if (result) onFinalised();
  }

  return (
    <span className="ml-auto flex flex-wrap items-center gap-2">
      {error && <span className="text-xs text-red-700">{error.message}</span>}
      {!confirming ? (
        <Button disabled={!ready} onClick={() => setConfirming(true)}>
          Finalise the result
        </Button>
      ) : (
        <>
          <span className="text-xs text-neutral-600">The result cannot be changed afterwards.</span>
          <Button busy={busy} onClick={() => void handleFinalise()}>
            Finalise now
          </Button>
          <Button variant="secondary" disabled={busy} onClick={() => setConfirming(false)}>
            Not yet
          </Button>
        </>
      )}
    </span>
  );
}
