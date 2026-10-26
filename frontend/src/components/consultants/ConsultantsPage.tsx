"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import { useMe } from "@/components/app/me-context";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardTitle, PageHeader } from "@/components/ui/Card";
import { ConfirmButton } from "@/components/ui/ConfirmButton";
import { EmptyState } from "@/components/ui/EmptyState";
import { TextField } from "@/components/ui/fields";
import { Loading } from "@/components/ui/Loading";
import { Modal } from "@/components/ui/Modal";
import { ApiError } from "@/lib/api/client";
import { changeGrantEndDate, grantAccess, listGrants, revokeGrant } from "@/lib/api/consultants";
import { getOrganisation } from "@/lib/api/organisation";
import type { ConsultantGrantOut, GrantStatus, OrganisationOut } from "@/lib/api/types";
import { formatDate } from "@/lib/format";
import { emailError, useSubmit } from "@/lib/forms";
import { canManage } from "@/lib/roles";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; org: OrganisationOut; grants: ConsultantGrantOut[] };

const STATUS_TONES: Record<GrantStatus, "amber" | "green" | "neutral" | "red"> = {
  waiting: "amber",
  active: "green",
  ended: "neutral",
  revoked: "red",
};

const STATUS_LABELS: Record<GrantStatus, string> = {
  waiting: "Waiting for the consultant",
  active: "Active",
  ended: "Ended",
  revoked: "Revoked",
};

/** The chosen day as an end-of-day UTC instant, as the consultant access emails explain. */
function endOfDayUtc(date: string): string {
  return `${date}T23:59:59Z`;
}

export function ConsultantsPage() {
  const { me } = useMe();
  const activeOrgId = me.active_organisation_id;
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    if (!activeOrgId) return;
    let cancelled = false;
    async function load() {
      setState({ kind: "loading" });
      try {
        const org = await getOrganisation();
        const grants = canManage(org.role) && org.status === "active" ? await listGrants() : [];
        if (!cancelled) setState({ kind: "ready", org, grants });
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
  }, [activeOrgId]);

  if (!activeOrgId) {
    return (
      <div className="space-y-4">
        <PageHeader title="Consultant access" />
        <Alert tone="info">Choose an organisation in the switcher above.</Alert>
      </div>
    );
  }

  if (state.kind === "loading") return <Loading>Loading consultant access...</Loading>;
  if (state.kind === "error") return <Alert tone="error">{state.message}</Alert>;

  const { org, grants } = state;
  if (!canManage(org.role) || org.status !== "active") {
    return (
      <div className="space-y-4">
        <PageHeader title="Consultant access" description={org.name} />
        <Alert tone="info">Only an owner or admin of an active organisation can manage this.</Alert>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Consultant access"
        description={`Give a consultant read-only access to ${org.name}'s results, until an end date you choose.`}
      />
      <GrantCard
        onGranted={(grant) =>
          setState((prev) =>
            prev.kind === "ready" ? { ...prev, grants: [grant, ...prev.grants] } : prev,
          )
        }
      />
      <GrantsCard
        grants={grants}
        onUpdated={(grant) =>
          setState((prev) =>
            prev.kind === "ready"
              ? { ...prev, grants: prev.grants.map((g) => (g.id === grant.id ? grant : g)) }
              : prev,
          )
        }
      />
    </div>
  );
}

function GrantCard({ onGranted }: { onGranted: (grant: ConsultantGrantOut) => void }) {
  const { busy, error, run } = useSubmit();
  const [email, setEmail] = useState("");
  const [emailFieldError, setEmailFieldError] = useState<string | undefined>(undefined);
  const [endDate, setEndDate] = useState("");
  const [dateError, setDateError] = useState<string | null>(null);
  const [grantedTo, setGrantedTo] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setGrantedTo(null);
    const invalidEmail = emailError(email);
    // Without a date, endOfDayUtc would send a malformed instant.
    const invalidDate = endDate ? null : "Choose an end date.";
    if (invalidEmail || invalidDate) {
      setEmailFieldError(invalidEmail);
      setDateError(invalidDate);
      return;
    }
    const grant = await run(() => grantAccess(email, endOfDayUtc(endDate)));
    if (grant) {
      onGranted(grant);
      setGrantedTo(grant.email);
      setEmail("");
      setEndDate("");
    }
  }

  return (
    <Card>
      <CardTitle>Give access</CardTitle>
      <p className="mt-1 text-sm text-neutral-600">
        We email the consultant a link to accept. Access ends at the end of the chosen day (UTC).
      </p>
      <form
        onSubmit={(e) => void handleSubmit(e)}
        className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end"
        noValidate
      >
        <div className="flex-1">
          <TextField
            label="Consultant's email"
            type="email"
            name="consultant_email"
            required
            error={emailFieldError}
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              setEmailFieldError(undefined);
            }}
          />
        </div>
        <div className="sm:w-48">
          <TextField
            label="Access ends on"
            type="date"
            name="expires_on"
            required
            error={dateError ?? undefined}
            value={endDate}
            onChange={(e) => {
              setEndDate(e.target.value);
              setDateError(null);
            }}
          />
        </div>
        <Button type="submit" busy={busy}>
          Give access
        </Button>
      </form>
      {error && (
        <div className="mt-3">
          <Alert tone="error">{error.message}</Alert>
        </div>
      )}
      {grantedTo && (
        <div className="mt-3">
          <Alert tone="success">Access granted. We sent an email to {grantedTo}.</Alert>
        </div>
      )}
    </Card>
  );
}

function GrantsCard({
  grants,
  onUpdated,
}: {
  grants: ConsultantGrantOut[];
  onUpdated: (grant: ConsultantGrantOut) => void;
}) {
  const { busy, error, run } = useSubmit();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [editing, setEditing] = useState<ConsultantGrantOut | null>(null);

  async function handleRevoke(id: string) {
    setBusyId(id);
    const grant = await run(() => revokeGrant(id));
    setBusyId(null);
    if (grant) onUpdated(grant);
  }

  return (
    <Card>
      <CardTitle>Access given</CardTitle>
      {error && (
        <div className="mt-3">
          <Alert tone="error">{error.message}</Alert>
        </div>
      )}
      {grants.length === 0 ? (
        <div className="mt-4">
          <EmptyState title="No consultant has access yet.">
            Give access above and the consultant appears here.
          </EmptyState>
        </div>
      ) : (
        <ul className="mt-2 divide-y divide-neutral-200">
          {grants.map((grant) => {
            const open = grant.status === "waiting" || grant.status === "active";
            return (
              <li
                key={grant.id}
                className="flex flex-wrap items-center gap-x-4 gap-y-2 py-3 text-sm"
              >
                <span className="font-medium text-neutral-900">{grant.email}</span>
                <Badge tone={STATUS_TONES[grant.status]}>{STATUS_LABELS[grant.status]}</Badge>
                <span className="text-neutral-600">
                  {grant.status === "revoked" && grant.revoked_at
                    ? `revoked ${formatDate(grant.revoked_at)}`
                    : `ends ${formatDate(grant.expires_at)}`}
                </span>
                {open && (
                  // One action at a time: every row waits while one is running.
                  <span className="ml-auto flex flex-wrap items-center gap-3">
                    <Button variant="secondary" disabled={busy} onClick={() => setEditing(grant)}>
                      Change end date
                    </Button>
                    <ConfirmButton
                      label="Revoke"
                      confirmLabel="End access now?"
                      busy={busy && busyId === grant.id}
                      disabled={busy && busyId !== grant.id}
                      onConfirm={() => void handleRevoke(grant.id)}
                    />
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {editing && (
        <EndDateModal
          grant={editing}
          onClose={() => setEditing(null)}
          onSaved={(grant) => {
            onUpdated(grant);
            setEditing(null);
          }}
        />
      )}
    </Card>
  );
}

/** Its own submit state, so a failure shows inside the dialog: while the dialog is open,
 * the page behind it is inert and an error there would go unseen. */
function EndDateModal({
  grant,
  onClose,
  onSaved,
}: {
  grant: ConsultantGrantOut;
  onClose: () => void;
  onSaved: (grant: ConsultantGrantOut) => void;
}) {
  const { busy, error, run } = useSubmit();
  const [newEndDate, setNewEndDate] = useState("");
  const [dateError, setDateError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    // Without a date, endOfDayUtc would send a malformed instant.
    if (!newEndDate) {
      setDateError("Choose an end date.");
      return;
    }
    const saved = await run(() => changeGrantEndDate(grant.id, endOfDayUtc(newEndDate)));
    if (saved) onSaved(saved);
  }

  return (
    <Modal open title="Change end date" onClose={onClose}>
      <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4" noValidate>
        {error && <Alert tone="error">{error.message}</Alert>}
        <TextField
          label={`New end date for ${grant.email}`}
          type="date"
          required
          hint="Access ends at the end of the chosen day (UTC)."
          error={dateError ?? undefined}
          value={newEndDate}
          onChange={(e) => {
            setNewEndDate(e.target.value);
            setDateError(null);
          }}
        />
        <div className="flex justify-end gap-3">
          <Button variant="secondary" disabled={busy} onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" busy={busy}>
            Save
          </Button>
        </div>
      </form>
    </Modal>
  );
}
