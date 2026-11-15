"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ADVICE_PARTS, getAdvice, requestAdvice, type AdviceRef } from "@/lib/api/advice";
import { ApiError } from "@/lib/api/client";
import type { AdviceOut, AdvicePartName } from "@/lib/api/types";

/** How often the page asks whether pending advice is ready, and for how long. */
export const POLL_MS = 2000;
const MAX_WAIT_MS = 5 * 60_000;

export type AdviceState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; advice: AdviceOut };

interface Held {
  /** The result this state belongs to; a state for another result reads as loading. */
  key: string;
  state: AdviceState;
  asking: boolean;
  askError: string | null;
}

/** One load or ask in flight. Cancelled when a newer one starts or the page goes away. */
interface Flight {
  cancelled: boolean;
}

function isPending(advice: AdviceOut): boolean {
  return ADVICE_PARTS.some((part) => advice[part].status === "pending");
}

function message(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback;
}

/** The advice on one result, kept fresh while any part is on its way. `ask` starts the
 * parts that have no answer yet, or asks again for `parts`. */
export function useAdvice(adviceRef: AdviceRef) {
  const { kind, assessmentId } = adviceRef;
  const ideaId = adviceRef.kind === "idea" ? adviceRef.ideaId : null;
  const key = `${kind}:${ideaId ?? ""}:${assessmentId}`;
  const target = useMemo<AdviceRef>(
    () =>
      kind === "idea" && ideaId !== null
        ? { kind: "idea", ideaId, assessmentId }
        : { kind: "readiness", assessmentId },
    [kind, ideaId, assessmentId],
  );
  const [held, setHeld] = useState<Held | null>(null);
  const flight = useRef<Flight | null>(null);

  const follow = useCallback(
    async (first: AdviceOut, mine: Flight) => {
      let advice = first;
      const show = (next: AdviceOut) =>
        setHeld({ key, state: { kind: "ready", advice: next }, asking: false, askError: null });
      show(advice);
      const giveUpAt = Date.now() + MAX_WAIT_MS;
      while (isPending(advice) && Date.now() < giveUpAt) {
        await new Promise((resolve) => setTimeout(resolve, POLL_MS));
        if (mine.cancelled) return;
        advice = await getAdvice(target);
        if (mine.cancelled) return;
        show(advice);
      }
    },
    [key, target],
  );

  useEffect(() => {
    const mine: Flight = { cancelled: false };
    flight.current = mine;
    getAdvice(target)
      .then((advice) => (mine.cancelled ? undefined : follow(advice, mine)))
      .catch((err: unknown) => {
        if (!mine.cancelled) {
          setHeld({
            key,
            state: { kind: "error", message: message(err, "Something went wrong.") },
            asking: false,
            askError: null,
          });
        }
      });
    return () => {
      mine.cancelled = true;
    };
  }, [key, target, follow]);

  const ask = useCallback(
    async (options: { parts?: AdvicePartName[]; regenerate?: boolean } = {}) => {
      if (flight.current) flight.current.cancelled = true;
      const mine: Flight = { cancelled: false };
      flight.current = mine;
      setHeld((now) => (now && now.key === key ? { ...now, asking: true, askError: null } : now));
      try {
        const advice = await requestAdvice(target, options);
        if (!mine.cancelled) await follow(advice, mine);
      } catch (err) {
        if (!mine.cancelled) {
          const askError = message(err, "We could not ask for advice. Please try again.");
          setHeld((now) => (now && now.key === key ? { ...now, asking: false, askError } : now));
        }
      }
    },
    [key, target, follow],
  );

  const mineNow = held && held.key === key ? held : null;
  return {
    state: mineNow ? mineNow.state : ({ kind: "loading" } as AdviceState),
    asking: mineNow?.asking ?? false,
    askError: mineNow?.askError ?? null,
    ask,
  };
}
