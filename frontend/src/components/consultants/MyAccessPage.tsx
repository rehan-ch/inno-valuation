"use client";

import { useEffect, useState } from "react";

import { useMe } from "@/components/app/me-context";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardTitle, PageHeader } from "@/components/ui/Card";
import { Loading } from "@/components/ui/Loading";
import { ApiError } from "@/lib/api/client";
import { acceptConsultantAccess, listConsultantAccess } from "@/lib/api/me";
import type { ConsultantAccessOut } from "@/lib/api/types";
import { formatDate } from "@/lib/format";
import { useSubmit } from "@/lib/forms";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; grants: ConsultantAccessOut[] };

/** The consultant's own side: access clients have given to their email. */
export function MyAccessPage() {
  const { refresh } = useMe();
  const [state, setState] = useState<State>({ kind: "loading" });
  const { busy, error, run } = useSubmit();
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listConsultantAccess()
      .then((grants) => {
        if (!cancelled) setState({ kind: "ready", grants });
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setState({
            kind: "error",
            message: err instanceof ApiError ? err.message : "Something went wrong.",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleAccept(grants: ConsultantAccessOut[], id: string) {
    setBusyId(id);
    const accepted = await run(() => acceptConsultantAccess(id));
    setBusyId(null);
    if (accepted) {
      setState({ kind: "ready", grants: grants.map((g) => (g.id === accepted.id ? accepted : g)) });
      await refresh(); // the organisation appears in the switcher
    }
  }

  if (state.kind === "loading") return <Loading>Loading your access...</Loading>;
  if (state.kind === "error") return <Alert tone="error">{state.message}</Alert>;

  const { grants } = state;
  return (
    <div className="space-y-6">
      <PageHeader
        title="My consulting access"
        description="Organisations whose results you can see as a consultant."
      />
      <Card>
        <CardTitle>Access given to you</CardTitle>
        {error && (
          <div className="mt-3">
            <Alert tone="error">{error.message}</Alert>
          </div>
        )}
        {grants.length === 0 ? (
          <p className="mt-2 text-sm text-neutral-600">
            No organisation has given you access yet. A client admin can invite you from their
            consultant access page.
          </p>
        ) : (
          <ul className="mt-2 divide-y divide-neutral-200">
            {grants.map((grant) => (
              <li
                key={grant.id}
                className="flex flex-wrap items-center gap-x-4 gap-y-2 py-3 text-sm"
              >
                <span className="font-medium text-neutral-900">{grant.organisation_name}</span>
                <Badge tone={grant.status === "active" ? "green" : "amber"}>
                  {grant.status === "active" ? "Active" : "Waiting for you"}
                </Badge>
                <span className="text-neutral-600">ends {formatDate(grant.expires_at)}</span>
                <span className="ml-auto">
                  {grant.status === "waiting" ? (
                    <Button
                      busy={busy && busyId === grant.id}
                      onClick={() => void handleAccept(grants, grant.id)}
                    >
                      Accept
                    </Button>
                  ) : (
                    <span className="text-neutral-500">
                      Open it from the organisation switcher above.
                    </span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
