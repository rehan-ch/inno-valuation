"use client";

import { useEffect, useState } from "react";

import { ApiError, getHealth } from "@/lib/api/client";
import type { HealthOut } from "@/lib/api/types";

type State =
  | { kind: "loading" }
  | { kind: "ready"; health: HealthOut }
  | { kind: "error"; code: string; message: string };

function StatusRow({ label, value, good }: { label: string; value: string; good: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4 py-3">
      <dt className="text-sm text-neutral-600">{label}</dt>
      <dd
        className={`text-sm font-medium ${good ? "text-green-700" : "text-red-700"}`}
        data-testid={`health-${label.toLowerCase().replace(/\s+/g, "-")}`}
      >
        {value}
      </dd>
    </div>
  );
}

export function HealthStatus() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();

    async function load() {
      try {
        const health = await getHealth({ signal: controller.signal });
        setState({ kind: "ready", health });
      } catch (err) {
        if (controller.signal.aborted) return;
        if (err instanceof ApiError) {
          setState({ kind: "error", code: err.code, message: err.message });
        } else {
          setState({
            kind: "error",
            code: "unknown_error",
            message: "Something went wrong.",
          });
        }
      }
    }

    void load();
    return () => controller.abort();
  }, []);

  if (state.kind === "loading") {
    return (
      <p role="status" aria-live="polite" className="text-sm text-neutral-600">
        Checking the API...
      </p>
    );
  }

  if (state.kind === "error") {
    return (
      <div role="alert" className="rounded-md border border-red-200 bg-red-50 p-4">
        <p className="text-sm font-medium text-red-800">We could not reach the API.</p>
        <p className="mt-1 text-sm text-red-700">{state.message}</p>
        <p className="mt-1 text-xs text-red-600">Error code: {state.code}</p>
      </div>
    );
  }

  const { health } = state;
  return (
    <dl className="divide-y divide-neutral-200 rounded-md border border-neutral-200 px-4">
      <StatusRow label="API" value={health.status === "ok" ? "OK" : health.status} good={health.status === "ok"} />
      <StatusRow
        label="Database"
        value={health.database === "ok" ? "OK" : "Error"}
        good={health.database === "ok"}
      />
      <StatusRow label="Version" value={health.version} good />
    </dl>
  );
}
