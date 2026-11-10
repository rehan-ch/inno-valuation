"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useMe } from "@/components/app/me-context";
import { Alert } from "@/components/ui/Alert";
import { Button, buttonClass } from "@/components/ui/Button";
import { Card, PageHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { SelectField } from "@/components/ui/fields";
import { Loading } from "@/components/ui/Loading";
import { Table, Td, Th } from "@/components/ui/Table";
import { auditExportUrl, getAuditFilters, listAuditEvents } from "@/lib/api/audit";
import type { AuditFilter } from "@/lib/api/audit";
import { ApiError } from "@/lib/api/client";
import type { AuditEventOut, AuditFiltersOut } from "@/lib/api/types";
import { formatDateTime } from "@/lib/format";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string; forbidden: boolean }
  | {
      kind: "ready";
      filters: AuditFiltersOut;
      events: AuditEventOut[];
      nextBefore: string | null;
    };

/** The organisation's activity log (P5.10): who did what and when, with the method version
 * and the AI model where they matter. Read-only: nothing here can change an entry. Owners
 * and admins filter it by action and person and download it. */
export function ActivityPage() {
  const { me } = useMe();
  const activeOrgId = me.active_organisation_id;
  const [state, setState] = useState<State>({ kind: "loading" });
  const [filter, setFilter] = useState<AuditFilter>({});
  const [loadingMore, setLoadingMore] = useState(false);
  const [moreError, setMoreError] = useState<string | null>(null);

  useEffect(() => {
    if (!activeOrgId) return;
    let cancelled = false;
    async function load() {
      try {
        const [filters, page] = await Promise.all([getAuditFilters(), listAuditEvents(filter)]);
        if (!cancelled) {
          setState({
            kind: "ready",
            filters,
            events: page.events,
            nextBefore: page.next_before,
          });
        }
      } catch (err) {
        if (!cancelled) {
          setState({
            kind: "error",
            message: err instanceof ApiError ? err.message : "Something went wrong.",
            forbidden: err instanceof ApiError && err.status === 403,
          });
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [activeOrgId, filter]);

  if (!activeOrgId) {
    return (
      <div className="space-y-4">
        <PageHeader title="Activity log" />
        <Alert tone="info">Choose an organisation in the switcher above.</Alert>
      </div>
    );
  }
  if (state.kind === "loading") return <Loading>Loading the activity log...</Loading>;
  if (state.kind === "error") {
    return (
      <div className="space-y-4">
        <PageHeader title="Activity log" />
        <Alert tone={state.forbidden ? "info" : "error"}>
          {state.forbidden
            ? "Only owners and admins can see the activity log."
            : state.message}
        </Alert>
      </div>
    );
  }

  const { filters, events, nextBefore } = state;
  const filtered = Boolean(filter.action || filter.actorId);

  async function loadMore() {
    if (!nextBefore) return;
    setLoadingMore(true);
    setMoreError(null);
    try {
      const page = await listAuditEvents(filter, nextBefore);
      setState((current) =>
        current.kind === "ready"
          ? {
              ...current,
              events: [...current.events, ...page.events],
              nextBefore: page.next_before,
            }
          : current,
      );
    } catch (err) {
      setMoreError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setLoadingMore(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Activity log"
        description="Who did what, and when. Entries are written as things happen and cannot be changed or removed."
        actions={
          <Link href="/organisation" className="text-sm font-medium text-primary hover:underline">
            Organisation settings
          </Link>
        }
      />
      <Card>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="flex flex-wrap items-end gap-3">
            <div className="w-60">
              <SelectField
                label="Action"
                compact
                value={filter.action ?? ""}
                onChange={(event) =>
                  setFilter((f) => ({ ...f, action: event.target.value || undefined }))
                }
              >
                <option value="">Every action</option>
                {filters.actions.map((action) => (
                  <option key={action.action} value={action.action}>
                    {action.label}
                  </option>
                ))}
              </SelectField>
            </div>
            <div className="w-52">
              <SelectField
                label="Person"
                compact
                value={filter.actorId ?? ""}
                onChange={(event) =>
                  setFilter((f) => ({ ...f, actorId: event.target.value || undefined }))
                }
              >
                <option value="">Everyone</option>
                {filters.actors.map((actor) => (
                  <option key={actor.id} value={actor.id}>
                    {actor.name}
                  </option>
                ))}
              </SelectField>
            </div>
            {filtered && (
              <Button variant="ghost" size="sm" onClick={() => setFilter({})}>
                Clear filters
              </Button>
            )}
          </div>
          <a href={auditExportUrl(filter)} className={buttonClass("secondary", "sm")} download>
            Export as CSV
          </a>
        </div>

        <div className="mt-4">
          {events.length === 0 ? (
            <EmptyState title={filtered ? "Nothing matches these filters" : "Nothing recorded yet"}>
              {filtered
                ? "Try another action or person."
                : "Actions such as inviting people, finalising an assessment and confirming an idea's scores appear here."}
            </EmptyState>
          ) : (
            <Table
              caption="Activity log, newest first"
              head={
                <>
                  <Th>When (UTC)</Th>
                  <Th>Who</Th>
                  <Th>What</Th>
                  <Th>Details</Th>
                </>
              }
            >
              {events.map((event) => (
                <tr key={event.id}>
                  <Td className="align-top whitespace-nowrap text-neutral-600 tabular-nums">
                    {formatDateTime(event.at)}
                  </Td>
                  <Td className="align-top">
                    {event.actor_name ?? (
                      <span className="text-neutral-500">Someone who has left</span>
                    )}
                  </Td>
                  <Td className="align-top">
                    <span className="font-medium text-neutral-900">{event.action_label}</span>
                    {event.subject && (
                      <span className="block text-neutral-600">{event.subject}</span>
                    )}
                  </Td>
                  <Td className="align-top text-neutral-600">
                    {event.detail}
                    {(event.question_set_version !== null || event.ai_model) && (
                      <span className="block text-xs text-neutral-500">
                        {[
                          event.question_set_version !== null
                            ? `Question set version ${event.question_set_version}`
                            : null,
                          event.ai_model ? `AI model ${event.ai_model}` : null,
                        ]
                          .filter(Boolean)
                          .join(" · ")}
                      </span>
                    )}
                  </Td>
                </tr>
              ))}
            </Table>
          )}
        </div>
        {moreError && (
          <div className="mt-3">
            <Alert tone="error">{moreError}</Alert>
          </div>
        )}
        {nextBefore && (
          <div className="mt-4 text-center">
            <Button variant="secondary" size="sm" busy={loadingMore} onClick={() => void loadMore()}>
              Show earlier entries
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}
