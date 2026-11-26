
"use client";

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import {
  ArrowRight,
  Building2,
  CalendarDays,
  CheckCircle2,
  Clock3,
  LockKeyhole,
  ShieldCheck,
} from "lucide-react";

import { useMe } from "@/components/app/me-context";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Loading } from "@/components/ui/Loading";
import { ApiError } from "@/lib/api/client";
import {
  acceptConsultantAccess,
  listConsultantAccess,
} from "@/lib/api/me";
import type { ConsultantAccessOut } from "@/lib/api/types";
import { formatDate } from "@/lib/format";
import { useSubmit } from "@/lib/forms";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; grants: ConsultantAccessOut[] };

export function MyAccessPage() {
  const { refresh } = useMe();
  const [state, setState] = useState<State>({
    kind: "loading",
  });
  const { busy, error, run } = useSubmit();
  const [busyId, setBusyId] = useState<string | null>(
    null,
  );

  useEffect(() => {
    let cancelled = false;

    listConsultantAccess()
      .then((grants) => {
        if (!cancelled) {
          setState({ kind: "ready", grants });
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setState({
            kind: "error",
            message:
              err instanceof ApiError
                ? err.message
                : "Something went wrong.",
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  async function handleAccept(id: string) {
    setBusyId(id);

    try {
      const accepted = await run(() =>
        acceptConsultantAccess(id),
      );

      if (accepted) {
        setState((prev) =>
          prev.kind === "ready"
            ? {
              ...prev,
              grants: prev.grants.map((grant) =>
                grant.id === accepted.id
                  ? accepted
                  : grant,
              ),
            }
            : prev,
        );

        await refresh();
      }
    } finally {
      setBusyId(null);
    }
  }

  if (state.kind === "loading") {
    return <Loading>Loading your access...</Loading>;
  }

  if (state.kind === "error") {
    return <Alert tone="error">{state.message}</Alert>;
  }

  const { grants } = state;
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
              CONSULTANT WORKSPACE
            </div>

            <h1 className="iv-consultants-heading">
              My consulting <span>access.</span>
            </h1>

            <p className="iv-consultants-subtitle">
              Manage invitations from organisations and
              access the innovation readiness results
              they&apos;ve shared with you.
            </p>

            <div className="iv-consultants-hero-meta">
              <span>
                <LockKeyhole
                  size={16}
                  aria-hidden="true"
                />
                Read-only access
              </span>
              <span>
                <ShieldCheck
                  size={16}
                  aria-hidden="true"
                />
                Secure collaboration
              </span>
            </div>
          </div>

          <div
            className="iv-consultants-hero-art"
            aria-hidden="true"
          >
            <div className="iv-consultants-orbit outer" />
            <div className="iv-consultants-orbit inner" />
            <div className="iv-consultants-shield">
              <Building2
                size={46}
                strokeWidth={1.4}
              />
            </div>
          </div>
        </header>

        <section
          className="iv-consultants-stats iv-consultants-enter"
          aria-label="Consulting access overview"
        >
          <AccessStat
            icon={<Building2 size={20} />}
            label="Organisations"
            value={grants.length}
            description="Shared with you"
          />
          <AccessStat
            icon={<CheckCircle2 size={20} />}
            label="Active workspaces"
            value={activeCount}
            description="Available to access"
          />
          <AccessStat
            icon={<Clock3 size={20} />}
            label="Invitations waiting"
            value={waitingCount}
            description="Pending your acceptance"
          />
        </section>

        <section className="iv-consultants-panel iv-consultants-enter">
          <div className="iv-consultants-panel-heading">
            <div className="iv-consultants-panel-icon">
              <Building2
                size={22}
                aria-hidden="true"
              />
            </div>

            <div>
              <div className="iv-consultants-small-label">
                YOUR CLIENT WORKSPACES
              </div>
              <h2>Access given to you</h2>
              <p>
                Review your invitations and available
                organisation workspaces.
              </p>
            </div>

            <span className="iv-consultants-count">
              {grants.length} total
            </span>
          </div>

          <div className="iv-consultants-panel-body">
            {error && (
              <div className="mb-4">
                <Alert tone="error">
                  {error.message}
                </Alert>
              </div>
            )}

            {grants.length === 0 ? (
              <div className="iv-consultants-empty">
                <div className="iv-consultants-empty-icon">
                  <Building2
                    size={32}
                    strokeWidth={1.5}
                  />
                </div>

                <h3>
                  No organisation has given you access yet.
                </h3>

                <p>
                  A client admin can invite you from their
                  consultant access page.
                </p>
              </div>
            ) : (
              <ul className="iv-consultants-grants">
                {grants.map((grant) => (
                  <li
                    key={grant.id}
                    className="iv-consultants-grant"
                  >
                    <div className="iv-consultants-grant-main">
                      <div
                        className={`iv-consultants-grant-avatar is-${grant.status}`}
                      >
                        <Building2
                          size={21}
                          aria-hidden="true"
                        />
                      </div>

                      <div className="iv-consultants-grant-details">
                        <strong>
                          {grant.organisation_name}
                        </strong>

                        <div className="iv-consultants-grant-meta">
                          <Badge
                            tone={
                              grant.status === "active"
                                ? "green"
                                : "amber"
                            }
                          >
                            {grant.status === "active"
                              ? "Active"
                              : "Waiting for you"}
                          </Badge>

                          <span>
                            <CalendarDays
                              size={14}
                              aria-hidden="true"
                            />
                            ends{" "}
                            {formatDate(grant.expires_at)}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="iv-consultants-grant-actions">
                      {grant.status === "waiting" ? (
                        <Button
                          busy={
                            busy &&
                            busyId === grant.id
                          }
                          onClick={() =>
                            void handleAccept(grant.id)
                          }
                        >
                          Accept
                        </Button>
                      ) : (
                        <span className="iv-consultants-access-note">
                          <CheckCircle2
                            size={16}
                            aria-hidden="true"
                          />
                          Open it from the organisation
                          switcher above.
                        </span>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>

        <footer className="iv-consultants-footer">
          <ShieldCheck
            size={18}
            aria-hidden="true"
          />
          <span>
            Organisations control the access they share
            with consultants.
          </span>
          <span className="iv-consultants-footer-end">
            Secure collaboration
            <ArrowRight
              size={15}
              aria-hidden="true"
            />
          </span>
        </footer>
      </div>
    </div>
  );
}

function AccessStat({
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
      <div
        className="iv-consultants-stat-icon"
        aria-hidden="true"
      >
        {icon}
      </div>
      <div>
        <p className="iv-consultants-stat-label">
          {label}
        </p>
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
