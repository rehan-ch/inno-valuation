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

import { Bar, ScaleChoice, StickyBar } from "./ScaleChoice";
import { saveFailureMessage } from "./status";

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
  const [saveError, setSaveError] = useState<string | null>(null);
  // Questions whose last change (agreed answer or note) failed to save. A later save that
  // works does not clear them: each stays marked until it is changed again.
  const [failed, setFailed] = useState<string[]>([]);
  // Saves run in order and the chain never rejects. The server's answer replaces the
  // screen only when no save is left in the queue, so quicker edits are never wiped.
  const queue = useRef<Promise<unknown>>(Promise.resolve());
  const pending = useRef(0);

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

  function showServer(consensus: ConsensusOut) {
    setState((prev) => (prev.kind === "ready" ? { ...prev, consensus } : prev));
  }

  function persist(questionId: string, changes: Parameters<typeof saveConsensus>[1]) {
    setFailed((prev) => prev.filter((id) => id !== questionId));
    setSave("saving");
    pending.current += 1;
    queue.current = queue.current
      .then(() => saveConsensus(assessmentId, changes))
      .then(
        (updated) => {
          pending.current -= 1;
          if (pending.current === 0) {
            setSave("saved");
            showServer(updated);
          }
        },
        async (err: unknown) => {
          pending.current -= 1;
          setSave("error");
          setSaveError(saveFailureMessage(err));
          setFailed((prev) => (prev.includes(questionId) ? prev : [...prev, questionId]));
          // Show what the server holds, so an unsaved answer is neither shown nor counted.
          if (pending.current === 0) {
            try {
              showServer(await getConsensus(assessmentId));
            } catch {
              // still offline: the error message stays
            }
          }
        },
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
    persist(questionId, { answers: { [questionId]: value } });
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

      <StickyBar>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <span className="text-sm font-medium text-neutral-900 tabular-nums">
            {agreedCount} of {consensus.question_count} agreed
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
              `Saved, but ${unsavedCount(failed.length)}. Change again where marked.`}
            {save === "error" && saveError}
          </span>
          <FinaliseControl
            assessmentId={assessmentId}
            waitForSaves={() => queue.current}
            ready={agreedCount === consensus.question_count}
            onFinalised={() => router.push(`/readiness/${assessmentId}/result`)}
          />
        </div>
        <Bar value={agreedCount} maximum={consensus.question_count} tone="accent" />
      </StickyBar>

      {questions.dimensions.map((dimension) => (
        <section
          key={dimension.key}
          aria-labelledby={`${dimension.key}-title`}
          className="rounded-lg border border-neutral-200 bg-white"
        >
          <div className="border-b border-neutral-200 px-5 py-4">
            <h2 id={`${dimension.key}-title`} className="text-sm font-semibold text-neutral-900">
              <span className="mr-2 text-neutral-400 tabular-nums">{dimension.order}.</span>
              {dimension.name}
            </h2>
          </div>
          <ol className="divide-y divide-neutral-100">
            {dimension.questions.map((question) => {
              const row = byQuestion.get(question.id);
              if (!row) return null;
              return (
                <ConsensusRow
                  key={question.id}
                  text={question.text}
                  row={row}
                  scale={scale}
                  failed={failed.includes(question.id)}
                  onAgree={(value) => agree(question.id, value)}
                  onNote={(note) =>
                    persist(question.id, { notes: { [question.id]: note || null } })
                  }
                />
              );
            })}
          </ol>
        </section>
      ))}
      <p className="text-sm">
        <Link href="/readiness" className="font-medium text-primary hover:underline">
          Back to assessments
        </Link>
      </p>
    </div>
  );
}

function unsavedCount(n: number): string {
  return n === 1 ? "1 change was not saved" : `${n} changes were not saved`;
}

function ConsensusRow({
  text,
  row,
  scale,
  failed,
  onAgree,
  onNote,
}: {
  text: string;
  row: QuestionConsensusOut;
  scale: number[];
  failed: boolean;
  onAgree: (value: number) => void;
  onNote: (note: string) => void;
}) {
  const [note, setNote] = useState(row.note ?? "");

  return (
    <li className={`px-5 py-4 ${row.wide_spread ? "border-l-2 border-l-amber-400 bg-amber-50/30" : ""}`}>
      <fieldset>
        <legend className="text-sm text-neutral-900">{text}</legend>
        {failed && (
          <p className="mt-1 text-xs font-medium text-red-700">
            Not saved. Set the agreed answer or note again.
          </p>
        )}
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-neutral-600">
          <span className="tabular-nums">
            {row.answers.map((a) => (
              <span key={a.user_id} className="mr-3 whitespace-nowrap">
                {a.name}: <strong className="font-semibold text-neutral-900">{a.answer}</strong>
              </span>
            ))}
          </span>
          {row.mean !== null && (
            <span className="tabular-nums">
              Average <strong className="font-semibold text-neutral-900">{row.mean}</strong>
            </span>
          )}
          {row.spread !== null && (
            <span className="tabular-nums">
              Spread <strong className="font-semibold text-neutral-900">{row.spread}</strong>
            </span>
          )}
          {row.wide_spread && <Badge tone="amber">Discuss: answers differ</Badge>}
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <span className="text-xs font-medium text-neutral-700">Agreed answer</span>
          <ScaleChoice
            name={`agreed-${row.question_id}`}
            scale={scale}
            value={row.agreed}
            onChange={onAgree}
            ariaLabel={(value) => `Agreed answer ${value}`}
          />
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
          className="block h-8 w-full max-w-xl rounded-md border border-neutral-300 bg-white px-2.5 text-[13px] text-neutral-900 shadow-xs placeholder:text-neutral-400 focus:outline-2 focus:-outline-offset-1 focus:outline-primary"
        />
      </label>
    </li>
  );
}

function FinaliseControl({
  assessmentId,
  ready,
  waitForSaves,
  onFinalised,
}: {
  assessmentId: string;
  ready: boolean;
  waitForSaves: () => Promise<unknown>;
  onFinalised: () => void;
}) {
  const { busy, error, run } = useSubmit();
  const [confirming, setConfirming] = useState(false);

  async function handleFinalise() {
    // The last agreed answer may still be saving; finalise only once every save has landed.
    const result = await run(async () => {
      await waitForSaves();
      return finaliseAssessment(assessmentId);
    });
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
