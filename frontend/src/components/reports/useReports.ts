"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError } from "@/lib/api/client";
import { listReports, requestReport, type ReportRef } from "@/lib/api/reports";
import type { ReportsOut } from "@/lib/api/types";

/** How often the page asks whether a report is drawn, and for how long. Drawing one takes
 * seconds; the person is also emailed when it is ready. */
export const POLL_MS = 2000;
export const MAX_WAIT_MS = 2 * 60_000;

export type ReportsState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; reports: ReportsOut };

interface Held {
  /** The result this state belongs to; a state for another result reads as loading. */
  key: string;
  state: ReportsState;
  asking: boolean;
  askError: string | null;
  /** The page stopped checking while the newest report was still being drawn. */
  stalled: boolean;
  /** A report the page was waiting for became ready (for screen readers). */
  arrived: boolean;
}

export function isDrawing(reports: ReportsOut): boolean {
  const newest = reports.reports[0];
  return newest !== undefined && (newest.status === "queued" || newest.status === "rendering");
}

function message(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback;
}

/** The reports of one result, kept fresh while the newest is being drawn. Everything in
 * flight belongs to one watch, dropped as a whole when the result changes or the page
 * goes, so a late answer never lands on another result. */
export function useReports(reportRef: ReportRef) {
  const { kind, assessmentId } = reportRef;
  const ideaId = reportRef.kind === "idea" ? reportRef.ideaId : null;
  const key = `${kind}:${ideaId ?? ""}:${assessmentId}`;
  const target = useMemo<ReportRef>(
    () =>
      kind === "idea" && ideaId !== null
        ? { kind: "idea", ideaId, assessmentId }
        : { kind: "readiness", assessmentId },
    [kind, ideaId, assessmentId],
  );
  const [held, setHeld] = useState<Held | null>(null);
  const watch = useRef<{ cancelled: boolean; timer: number | null; giveUpAt: number } | null>(
    null,
  );

  const update = useCallback(
    (change: (now: Held) => Held) => setHeld((now) => (now && now.key === key ? change(now) : now)),
    [key],
  );

  /** Check again in a moment while the newest report is being drawn. */
  const follow = useCallback(
    (reports: ReportsOut) => {
      const mine = watch.current;
      if (!mine || mine.cancelled || mine.timer !== null || !isDrawing(reports)) return;
      if (Date.now() > mine.giveUpAt) {
        update((now) => ({ ...now, stalled: true }));
        return;
      }
      mine.timer = window.setTimeout(() => {
        mine.timer = null;
        listReports(target).then(
          (fresh) => {
            if (mine.cancelled) return;
            update((now) => ({
              ...now,
              state: { kind: "ready", reports: fresh },
              arrived: now.arrived || (!isDrawing(fresh) && fresh.reports[0]?.status === "ready"),
            }));
            follow(fresh);
          },
          () => {
            // One failed check stops the loop; "Check again" restarts it.
            if (!mine.cancelled) update((now) => ({ ...now, stalled: true }));
          },
        );
      }, POLL_MS);
    },
    [target, update],
  );

  useEffect(() => {
    const mine = { cancelled: false, timer: null as number | null, giveUpAt: Date.now() + MAX_WAIT_MS };
    watch.current = mine;
    setHeld({
      key,
      state: { kind: "loading" },
      asking: false,
      askError: null,
      stalled: false,
      arrived: false,
    });
    listReports(target).then(
      (reports) => {
        if (mine.cancelled) return;
        setHeld((now) => (now && now.key === key ? { ...now, state: { kind: "ready", reports } } : now));
        follow(reports);
      },
      (err: unknown) => {
        if (mine.cancelled) return;
        setHeld((now) =>
          now && now.key === key
            ? { ...now, state: { kind: "error", message: message(err, "Could not load the reports.") } }
            : now,
        );
      },
    );
    return () => {
      mine.cancelled = true;
      if (mine.timer !== null) window.clearTimeout(mine.timer);
    };
  }, [key, target, follow]);

  const ask = useCallback(async () => {
    const mine = watch.current;
    if (!mine) return;
    update((now) => ({ ...now, asking: true, askError: null, stalled: false, arrived: false }));
    try {
      const reports = await requestReport(target);
      if (mine.cancelled) return;
      mine.giveUpAt = Date.now() + MAX_WAIT_MS;
      update((now) => ({ ...now, asking: false, state: { kind: "ready", reports } }));
      follow(reports);
    } catch (err) {
      if (!mine.cancelled) {
        update((now) => ({
          ...now,
          asking: false,
          askError: message(err, "Could not make the report."),
        }));
      }
    }
  }, [target, update, follow]);

  const checkAgain = useCallback(() => {
    const mine = watch.current;
    if (!mine || held?.state.kind !== "ready") return;
    mine.giveUpAt = Date.now() + MAX_WAIT_MS;
    update((now) => ({ ...now, stalled: false }));
    follow(held.state.reports);
  }, [held, update, follow]);

  const current = held && held.key === key ? held : null;
  return {
    state: current?.state ?? ({ kind: "loading" } as ReportsState),
    asking: current?.asking ?? false,
    askError: current?.askError ?? null,
    stalled: current?.stalled ?? false,
    arrived: current?.arrived ?? false,
    ask,
    checkAgain,
    target,
  };
}
