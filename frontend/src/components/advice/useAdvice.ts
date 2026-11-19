"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ADVICE_PARTS, getAdvice, requestAdvice, type AdviceRef } from "@/lib/api/advice";
import { ApiError } from "@/lib/api/client";
import type { AdviceOut, AdvicePartName } from "@/lib/api/types";

/** How often the page asks whether pending advice is ready, and for how long. */
export const POLL_MS = 2000;
export const MAX_WAIT_MS = 5 * 60_000;
/** How many checks in a row may fail before the page stops and offers "Check again". */
export const MAX_FAILED_POLLS = 3;

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
  /** The page stopped checking while a part was still on its way. */
  stalled: boolean;
  /** Pending advice arrived while the page was open (for screen readers). */
  arrived: boolean;
}

/** Everything in flight for one result on one mounted page: the first load, every ask and
 * the one polling loop. Cancelled as a whole when the result changes or the page goes. */
interface Watch {
  cancelled: boolean;
  polling: boolean;
  /** The newest advice the server sent, and how many asks have been answered. A check
   * that was sent before an ask was answered is dropped: it describes the time before. */
  latest: AdviceOut | null;
  asks: number;
  giveUpAt: number;
}

function isPending(advice: AdviceOut): boolean {
  return ADVICE_PARTS.some((part) => advice[part].status === "pending");
}

function message(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback;
}

/** The advice on one result, kept fresh while any part is on its way. `ask` starts the
 * parts that have no answer yet, or asks again for `parts`. When the wait runs out or the
 * checks keep failing, `stalled` is true and `checkAgain` starts checking again. */
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
  const watch = useRef<Watch | null>(null);

  /** Change the state of this result, unless the page has moved on to another one. */
  const update = useCallback(
    (change: (now: Held) => Held) => setHeld((now) => (now && now.key === key ? change(now) : now)),
    [key],
  );

  /** The one polling loop of a watch. Starting it while it runs does nothing: the running
   * loop already follows `mine.latest`. An ask that fails never touches it. */
  const poll = useCallback(
    async (mine: Watch, immediately = false) => {
      if (mine.polling || mine.cancelled) return;
      mine.polling = true;
      let failures = 0;
      let wait = !immediately;
      try {
        while (mine.latest && isPending(mine.latest)) {
          if (Date.now() >= mine.giveUpAt) {
            update((now) => ({ ...now, stalled: true }));
            return;
          }
          if (wait) await new Promise((resolve) => setTimeout(resolve, POLL_MS));
          wait = true;
          if (mine.cancelled) return;
          const asks = mine.asks;
          let advice: AdviceOut;
          try {
            advice = await getAdvice(target);
          } catch {
            if (mine.cancelled) return;
            failures += 1;
            if (failures >= MAX_FAILED_POLLS) {
              // What is on screen stays; the reader can check again.
              update((now) => ({ ...now, stalled: true }));
              return;
            }
            continue;
          }
          if (mine.cancelled) return;
          failures = 0;
          if (asks !== mine.asks) continue;
          mine.latest = advice;
          const arrived = !isPending(advice);
          update((now) => ({
            ...now,
            state: { kind: "ready", advice },
            arrived: now.arrived || arrived,
          }));
        }
      } finally {
        mine.polling = false;
      }
    },
    [target, update],
  );

  useEffect(() => {
    const mine: Watch = {
      cancelled: false,
      polling: false,
      latest: null,
      asks: 0,
      giveUpAt: Date.now() + MAX_WAIT_MS,
    };
    watch.current = mine;
    getAdvice(target)
      .then((advice) => {
        if (mine.cancelled || mine.asks > 0) return;
        mine.latest = advice;
        setHeld({
          key,
          state: { kind: "ready", advice },
          asking: false,
          askError: null,
          stalled: false,
          arrived: false,
        });
        void poll(mine);
      })
      .catch((err: unknown) => {
        if (mine.cancelled || mine.latest) return;
        setHeld({
          key,
          state: { kind: "error", message: message(err, "Something went wrong.") },
          asking: false,
          askError: null,
          stalled: false,
          arrived: false,
        });
      });
    return () => {
      // Stops the first load, any ask and the polling loop together.
      mine.cancelled = true;
    };
  }, [key, target, poll]);

  const ask = useCallback(
    async (options: { parts?: AdvicePartName[]; regenerate?: boolean } = {}) => {
      const mine = watch.current;
      if (!mine || mine.cancelled) return;
      update((now) => ({ ...now, asking: true, askError: null }));
      try {
        const advice = await requestAdvice(target, options);
        if (mine.cancelled) return;
        mine.asks += 1;
        mine.latest = advice;
        mine.giveUpAt = Date.now() + MAX_WAIT_MS;
        setHeld({
          key,
          state: { kind: "ready", advice },
          asking: false,
          askError: null,
          stalled: false,
          arrived: false,
        });
        void poll(mine);
      } catch (err) {
        if (mine.cancelled) return;
        const askError = message(err, "We could not ask for advice. Please try again.");
        update((now) => ({ ...now, asking: false, askError }));
      }
    },
    [key, target, poll, update],
  );

  const checkAgain = useCallback(() => {
    const mine = watch.current;
    if (!mine || mine.cancelled) return;
    mine.giveUpAt = Date.now() + MAX_WAIT_MS;
    update((now) => ({ ...now, stalled: false }));
    void poll(mine, true);
  }, [poll, update]);

  const mineNow = held && held.key === key ? held : null;
  return {
    state: mineNow ? mineNow.state : ({ kind: "loading" } as AdviceState),
    asking: mineNow?.asking ?? false,
    askError: mineNow?.askError ?? null,
    stalled: mineNow?.stalled ?? false,
    arrived: mineNow?.arrived ?? false,
    ask,
    checkAgain,
  };
}
