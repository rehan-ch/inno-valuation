
"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import type { ReactNode } from "react";
import {
  ArrowRight,
  CalendarDays,
  Check,
  CheckCircle2,
  Clock3,
  ExternalLink,
  LockKeyhole,
  Mail,
  ShieldCheck,
  ShieldOff,
  Sparkles,
  UsersRound,
} from "lucide-react";

import { useMe } from "@/components/app/me-context";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmButton } from "@/components/ui/ConfirmButton";
import { EmptyState } from "@/components/ui/EmptyState";
import { TextField } from "@/components/ui/fields";
import { Loading } from "@/components/ui/Loading";
import { Modal } from "@/components/ui/Modal";
import { ApiError } from "@/lib/api/client";
import {
  changeGrantEndDate,
  grantAccess,
  listGrants,
  revokeGrant,
} from "@/lib/api/consultants";
import { getOrganisation } from "@/lib/api/organisation";
import type {
  ConsultantGrantOut,
  GrantStatus,
  OrganisationOut,
} from "@/lib/api/types";
import { formatDate } from "@/lib/format";
import { emailError, useSubmit } from "@/lib/forms";
import { canManage } from "@/lib/roles";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | {
    kind: "ready";
    org: OrganisationOut;
    grants: ConsultantGrantOut[];
  };

const STATUS_TONES: Record<
  GrantStatus,
  "amber" | "green" | "neutral" | "red"
> = {
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

function endOfDayUtc(date: string): string {
  return `${date}T23:59:59Z`;
}

function GrantIcon({ status }: { status: GrantStatus }) {
  if (status === "active") {
    return <CheckCircle2 size={21} aria-hidden="true" />;
  }
  if (status === "waiting") {
    return <Clock3 size={21} aria-hidden="true" />;
  }
  if (status === "revoked") {
    return <ShieldOff size={21} aria-hidden="true" />;
  }
  return <CalendarDays size={21} aria-hidden="true" />;
}

export function ConsultantsPage() {
  const { me } = useMe();
  const activeOrgId = me.active_organisation_id;
  const [state, setState] = useState<State>({
    kind: "loading",
  });

  useEffect(() => {
    if (!activeOrgId) return;

    let cancelled = false;

    async function load() {
      setState({ kind: "loading" });

      try {
        const org = await getOrganisation();
        const grants =
          canManage(org.role) && org.status === "active"
            ? await listGrants()
            : [];

        if (!cancelled) {
          setState({ kind: "ready", org, grants });
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
  }, [activeOrgId]);

  if (!activeOrgId) {
    return (
      <div className="iv-consultants">
        <div className="iv-consultants-shell">
          <h1 className="iv-consultants-heading">
            Consultant access
          </h1>
          <Alert tone="info">
            Choose an organisation in the switcher above.
          </Alert>
        </div>
      </div>
    );
  }

  if (state.kind === "loading") {
    return <Loading>Loading consultant access...</Loading>;
  }

  if (state.kind === "error") {
    return <Alert tone="error">{state.message}</Alert>;
  }

  const { org, grants } = state;

  if (!canManage(org.role) || org.status !== "active") {
    return (
      <div className="iv-consultants">
        <div className="iv-consultants-shell">
          <h1 className="iv-consultants-heading">
            Consultant access
          </h1>
          <p className="iv-consultants-subtitle">
            {org.name}
          </p>
          <Alert tone="info">
            Only an owner or admin of an active organisation can
            manage this.
          </Alert>
        </div>
      </div>
    );
  }

  const activeCount = grants.filter(
    (grant) => grant.status === "active",
  ).length;
  const waitingCount = grants.filter(
    (grant) => grant.status === "waiting",
  ).length;

  return (
    <div className="iv-consultants">
      <div className="iv-consultants-shell">
        <header className="iv-consultants-hero iv-consultants-enter">
          <div className="iv-consultants-hero-copy">
            <div className="iv-consultants-eyebrow">
              <span className="iv-consultants-eyebrow-dot" />
              EXTERNAL COLLABORATION
            </div>

            <h1 className="iv-consultants-heading">
              Consultant <span>access.</span>
            </h1>

            <p className="iv-consultants-subtitle">
              Collaborate with trusted experts while keeping
              your organisation&apos;s information protected.
              Manage read-only access to {org.name}&apos;s
              results in one place.
            </p>

            <div className="iv-consultants-hero-meta">
              <span>
                <ShieldCheck size={16} aria-hidden="true" />
                Read-only permissions
              </span>
              <span>
                <CalendarDays size={16} aria-hidden="true" />
                Time-limited access
              </span>
            </div>
          </div>

          <div className="iv-consultants-hero-art" aria-hidden="true">
            <div className="iv-consultants-orbit outer" />
            <div className="iv-consultants-orbit inner" />
            <div className="iv-consultants-shield">
              <ShieldCheck size={49} strokeWidth={1.35} />
            </div>
            <span className="iv-consultants-orbit-point point-one">
              <LockKeyhole size={15} />
            </span>
            <span className="iv-consultants-orbit-point point-two">
              <Check size={15} />
            </span>
          </div>
        </header>

        <section
          className="iv-consultants-stats iv-consultants-enter"
          aria-label="Access overview"
        >
          <StatCard
            icon={<UsersRound size={20} />}
            label="Total access records"
            value={grants.length}
            description="All consultant invitations"
          />
          <StatCard
            icon={<ShieldCheck size={20} />}
            label="Active access"
            value={activeCount}
            description="Consultants with access"
          />
          <StatCard
            icon={<Clock3 size={20} />}
            label="Pending invitations"
            value={waitingCount}
            description="Awaiting acceptance"
          />
        </section>

        <div className="iv-consultants-content">
          <GrantCard
            onGranted={(grant) =>
              setState((prev) =>
                prev.kind === "ready"
                  ? {
                    ...prev,
                    grants: [grant, ...prev.grants],
                  }
                  : prev,
              )
            }
          />

          <GrantsCard
            grants={grants}
            onUpdated={(grant) =>
              setState((prev) =>
                prev.kind === "ready"
                  ? {
                    ...prev,
                    grants: prev.grants.map((item) =>
                      item.id === grant.id ? grant : item,
                    ),
                  }
                  : prev,
              )
            }
          />
        </div>

        <footer className="iv-consultants-footer">
          <ShieldCheck size={19} aria-hidden="true" />
          <span>
            Consultant access is read-only and controlled by
            your organisation.
          </span>
          <span className="iv-consultants-footer-end">
            Secure collaboration
            <ExternalLink size={15} aria-hidden="true" />
          </span>
        </footer>
      </div>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  description,
}: {
  icon: ReactNode;
  label: string;
  value: number;
  description: string;
}) {
  return (
    <div className="iv-consultants-stat">
      <div className="iv-consultants-stat-icon" aria-hidden="true">
        {icon}
      </div>
      <div>
        <p className="iv-consultants-stat-label">{label}</p>
        <strong className="iv-consultants-stat-value">
          {value}
        </strong>
        <p className="iv-consultants-stat-description">
          {description}
        </p>
      </div>
    </div>
  );
}

function GrantCard({
  onGranted,
}: {
  onGranted: (grant: ConsultantGrantOut) => void;
}) {
  const { busy, error, run } = useSubmit();

  const [email, setEmail] = useState("");
  const [emailFieldError, setEmailFieldError] =
    useState<string | undefined>(undefined);
  const [endDate, setEndDate] = useState("");
  const [dateError, setDateError] = useState<string | null>(
    null,
  );
  const [grantedTo, setGrantedTo] = useState<string | null>(
    null,
  );

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setGrantedTo(null);

    const invalidEmail = emailError(email);
    const invalidDate = endDate
      ? null
      : "Choose an end date.";

    if (invalidEmail || invalidDate) {
      setEmailFieldError(invalidEmail);
      setDateError(invalidDate);
      return;
    }

    const grant = await run(() =>
      grantAccess(email, endOfDayUtc(endDate)),
    );

    if (grant) {
      onGranted(grant);
      setGrantedTo(grant.email);
      setEmail("");
      setEndDate("");
    }
  }

  return (
    <section className="iv-consultants-panel iv-consultants-enter">
      <div className="iv-consultants-panel-heading">
        <div className="iv-consultants-panel-icon">
          <Mail size={21} aria-hidden="true" />
        </div>

        <div>
          <div className="iv-consultants-small-label">
            INVITE A CONSULTANT
          </div>
          <h2>Give access</h2>
          <p>
            Invite a consultant to review your organisation&apos;s
            results securely.
          </p>
        </div>
      </div>

      <div className="iv-consultants-panel-body">
        <div className="iv-consultants-instruction">
          <Sparkles size={18} aria-hidden="true" />
          <p>
            We&apos;ll email an invitation link. Access
            automatically ends at the end of your chosen day
            (UTC).
          </p>
        </div>

        <form
          onSubmit={(event) => void handleSubmit(event)}
          className="iv-consultants-invite-form"
          noValidate
        >
          <div className="iv-consultants-field">
            <TextField
              label="Consultant's email"
              type="email"
              name="consultant_email"
              required
              error={emailFieldError}
              value={email}
              onChange={(event) => {
                setEmail(event.target.value);
                setEmailFieldError(undefined);
              }}
            />
          </div>

          <div className="iv-consultants-field iv-consultants-date">
            <TextField
              label="Access ends on"
              type="date"
              name="expires_on"
              required
              error={dateError ?? undefined}
              value={endDate}
              onChange={(event) => {
                setEndDate(event.target.value);
                setDateError(null);
              }}
            />
          </div>

          <div className="iv-consultants-submit">
            <Button type="submit" busy={busy}>
              Give access
            </Button>
            <ArrowRight size={17} aria-hidden="true" />
          </div>
        </form>

        {error && (
          <div className="mt-4">
            <Alert tone="error">{error.message}</Alert>
          </div>
        )}

        {grantedTo && (
          <div className="mt-4">
            <Alert tone="success">
              Access granted. We sent an email to {grantedTo}.
            </Alert>
          </div>
        )}
      </div>
    </section>
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

  const {
    busy: dateBusy,
    error: dateSubmitError,
    run: runDateSubmit,
    clearError: clearDateSubmitError,
  } = useSubmit();

  const [busyId, setBusyId] = useState<string | null>(
    null,
  );
  const [editingId, setEditingId] = useState<string | null>(
    null,
  );
  const [newEndDate, setNewEndDate] = useState("");
  const [dateError, setDateError] = useState<string | null>(
    null,
  );

  async function handleRevoke(id: string) {
    setBusyId(id);
    try {
      const grant = await run(() => revokeGrant(id));
      if (grant) onUpdated(grant);
    } finally {
      setBusyId(null);
    }
  }

  async function handleEndDateChange(
    event: FormEvent,
    id: string,
  ) {
    event.preventDefault();

    if (!newEndDate) {
      setDateError("Choose an end date.");
      return;
    }

    setBusyId(id);

    try {
      const grant = await runDateSubmit(() =>
        changeGrantEndDate(id, endOfDayUtc(newEndDate)),
      );

      if (grant) {
        onUpdated(grant);
        setEditingId(null);
        setNewEndDate("");
        setDateError(null);
      }
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="iv-consultants-panel iv-consultants-enter">
      <div className="iv-consultants-panel-heading">
        <div className="iv-consultants-panel-icon">
          <UsersRound size={21} aria-hidden="true" />
        </div>

        <div>
          <div className="iv-consultants-small-label">
            ACCESS DIRECTORY
          </div>
          <h2>Access given</h2>
          <p>
            Monitor invitations and control existing
            consultant permissions.
          </p>
        </div>

        <span className="iv-consultants-count">
          {grants.length} total
        </span>
      </div>

      <div className="iv-consultants-panel-body">
        {error && (
          <div className="mb-4">
            <Alert tone="error">{error.message}</Alert>
          </div>
        )}

        {grants.length === 0 ? (
          <div className="iv-consultants-empty">
            <div className="iv-consultants-empty-icon">
              <ShieldCheck size={31} strokeWidth={1.5} />
            </div>

            <EmptyState title="No consultant has access yet.">
              Give access above and the consultant appears here.
            </EmptyState>
          </div>
        ) : (
          <ul className="iv-consultants-grants">
            {grants.map((grant) => {
              const open =
                grant.status === "waiting" ||
                grant.status === "active";

              return (
                <li
                  key={grant.id}
                  className="iv-consultants-grant"
                >
                  <div className="iv-consultants-grant-main">
                    <div
                      className={`iv-consultants-grant-avatar is-${grant.status}`}
                    >
                      <GrantIcon status={grant.status} />
                    </div>

                    <div className="iv-consultants-grant-details">
                      <strong>{grant.email}</strong>
                      <div className="iv-consultants-grant-meta">
                        <Badge tone={STATUS_TONES[grant.status]}>
                          {STATUS_LABELS[grant.status]}
                        </Badge>

                        <span>
                          <CalendarDays
                            size={14}
                            aria-hidden="true"
                          />
                          {grant.status === "revoked" &&
                            grant.revoked_at
                            ? `revoked ${formatDate(grant.revoked_at)}`
                            : `ends ${formatDate(grant.expires_at)}`}
                        </span>
                      </div>
                    </div>
                  </div>

                  {open && (
                    <div className="iv-consultants-grant-actions">
                      <Button
                        variant="secondary"
                        disabled={busy || dateBusy}
                        onClick={() => {
                          setEditingId(grant.id);
                          setNewEndDate("");
                          setDateError(null);
                          // One dialog's failed save is not the next dialog's error.
                          clearDateSubmitError();
                        }}
                      >
                        Change end date
                      </Button>

                      <ConfirmButton
                        label="Revoke"
                        confirmLabel="End access now?"
                        busy={busy && busyId === grant.id}
                        disabled={dateBusy || (busy && busyId !== grant.id)}
                        onConfirm={() =>
                          void handleRevoke(grant.id)
                        }
                      />
                    </div>
                  )}

                  {editingId === grant.id && (
                    <Modal
                      open
                      title="Change end date"
                      onClose={() => setEditingId(null)}
                    >
                      <form
                        onSubmit={(event) =>
                          void handleEndDateChange(
                            event,
                            grant.id,
                          )
                        }
                        className="iv-consultants-modal-form"
                        noValidate
                      >
                        <div className="iv-consultants-date">
                          <TextField
                            label={`New end date for ${grant.email}`}
                            type="date"
                            required
                            hint="Access ends at the end of the chosen day (UTC)."
                            error={dateError ?? undefined}
                            value={newEndDate}
                            onChange={(event) => {
                              setNewEndDate(event.target.value);
                              setDateError(null);
                            }}
                          />
                        </div>

                        {dateSubmitError && (
                          <Alert tone="error">
                            {dateSubmitError.message}
                          </Alert>
                        )}

                        <div className="flex flex-wrap justify-end gap-3">
                          <Button
                            variant="secondary"
                            disabled={dateBusy}
                            onClick={() =>
                              setEditingId(null)
                            }
                          >
                            Cancel
                          </Button>
                          <Button
                            type="submit"
                            busy={dateBusy}
                          >
                            Save
                          </Button>
                        </div>
                      </form>
                    </Modal>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}
