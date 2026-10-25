"use client";

import { useEffect, useRef, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Loading } from "@/components/ui/Loading";
import { ApiError } from "@/lib/api/client";
import { explainQuestion, getExplanation } from "@/lib/api/readiness";
import type { ExplanationOut } from "@/lib/api/types";

/** How often the page asks whether a pending explanation is ready, and for how long. */
export const POLL_MS = 1500;
const MAX_WAIT_MS = 60_000;

type State =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ready"; explanation: ExplanationOut }
  | { kind: "failed"; message: string };

const FAILED = "We could not explain this question right now. Please try again.";
const TOO_SLOW = "This is taking longer than usual. Please try again in a moment.";

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** "What does this mean?" under a readiness question (AI touchpoint 1). The explanation is
 * written in the background and saved for everyone in the organisation, so the first ask
 * may wait a few seconds and later ones are instant. Helps only; it never suggests an
 * answer. */
export function QuestionExplanation({
  questionId,
  version,
}: {
  questionId: string;
  version: number;
}) {
  const [open, setOpen] = useState(false);
  const [state, setState] = useState<State>({ kind: "idle" });
  // Stops polling once the question leaves the page.
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  async function ask() {
    setState({ kind: "loading" });
    try {
      let explanation = await explainQuestion(questionId, version);
      const giveUpAt = Date.now() + MAX_WAIT_MS;
      while (explanation.status === "pending") {
        if (Date.now() > giveUpAt) {
          if (mounted.current) setState({ kind: "failed", message: TOO_SLOW });
          return;
        }
        await sleep(POLL_MS);
        if (!mounted.current) return;
        explanation = await getExplanation(questionId, version);
      }
      if (!mounted.current) return;
      setState(
        explanation.status === "ready"
          ? { kind: "ready", explanation }
          : { kind: "failed", message: FAILED },
      );
    } catch (err) {
      if (mounted.current) {
        setState({ kind: "failed", message: err instanceof ApiError ? err.message : FAILED });
      }
    }
  }

  function toggle() {
    const opening = !open;
    setOpen(opening);
    if (opening && (state.kind === "idle" || state.kind === "failed")) void ask();
  }

  const panelId = `${questionId}-explanation`;
  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        aria-controls={panelId}
        className="text-xs font-medium text-primary hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
      >
        {open ? "Hide the explanation" : "What does this mean?"}
      </button>
      {open && (
        <div
          id={panelId}
          className="mt-2 rounded-xl border border-neutral-200 bg-neutral-50 p-3 text-sm"
        >
          {state.kind === "loading" && <Loading>Writing a plain explanation...</Loading>}
          {state.kind === "failed" && (
            <div className="space-y-2">
              <Alert tone="error">{state.message}</Alert>
              <Button variant="secondary" onClick={() => void ask()}>
                Try again
              </Button>
            </div>
          )}
          {state.kind === "ready" && <Explanation explanation={state.explanation} />}
        </div>
      )}
    </div>
  );
}

function Explanation({ explanation }: { explanation: ExplanationOut }) {
  return (
    <div className="space-y-2 text-neutral-800">
      <p>{(explanation.explanation ?? []).join(" ")}</p>
      {explanation.example && (
        <p>
          <span className="font-medium text-neutral-900">For example: </span>
          {explanation.example}
        </p>
      )}
      <p className="text-xs text-neutral-500">
        {explanation.sample
          ? "Sample text: the AI is not connected yet."
          : `Written by AI about ${explanation.dimension_name}. It can be wrong, so use your own judgement.`}
      </p>
    </div>
  );
}
