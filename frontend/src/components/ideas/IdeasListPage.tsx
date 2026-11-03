"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { useMe } from "@/components/app/me-context";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button, buttonClass } from "@/components/ui/Button";
import { Card, CardDescription, CardTitle, PageHeader } from "@/components/ui/Card";
import { CheckboxField } from "@/components/ui/fields";
import { EmptyState } from "@/components/ui/EmptyState";
import { Loading } from "@/components/ui/Loading";
import { Table, Td, Th } from "@/components/ui/Table";
import { ApiError } from "@/lib/api/client";
import { assessmentHref, listIdeas } from "@/lib/api/ideas";
import type { IdeaSummaryOut } from "@/lib/api/types";
import { formatDate } from "@/lib/format";
import { formatMoney } from "@/lib/money";
import { activeMembership, canManage } from "@/lib/roles";

import { IDEA_STATUS_LABELS, IDEA_STATUS_TONES, STAGE_LABELS, assessmentLabel } from "./status";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; ideas: IdeaSummaryOut[] };

type Sort = "newest" | "iq" | "vfm";

const SORT_LABELS: Record<Sort, string> = {
  newest: "Newest first",
  iq: "Highest IQ first",
  vfm: "Best value for money first",
};

/** The confirmed IQ of an idea's latest assessment, or null. */
function iqOf(idea: IdeaSummaryOut): number | null {
  const latest = idea.latest_assessment;
  return latest?.status === "confirmed" && latest.iq !== null ? Number(latest.iq) : null;
}

function vfmOf(idea: IdeaSummaryOut): number | null {
  const latest = idea.latest_assessment;
  return latest?.status === "confirmed" && latest.vfm_per_point !== null
    ? Number(latest.vfm_per_point)
    : null;
}

/** Sort ideas; those without the figure go last, in their existing order. */
export function sortIdeas(ideas: IdeaSummaryOut[], sort: Sort): IdeaSummaryOut[] {
  if (sort === "newest") return ideas;
  const value = sort === "iq" ? iqOf : vfmOf;
  return [...ideas].sort((a, b) => {
    const x = value(a);
    const y = value(b);
    if (x === null && y === null) return 0;
    if (x === null) return 1;
    if (y === null) return -1;
    return sort === "iq" ? y - x : x - y; // IQ: higher is better; VfM: lower is better
  });
}

/** The organisation's ideas with their IQ and Value for Money, sortable and comparable. */
export function IdeasListPage() {
  const { me } = useMe();
  const activeOrgId = me.active_organisation_id;
  const membership = activeMembership(me);
  const canAdd =
    membership !== null &&
    membership.organisation_status === "active" &&
    membership.role !== "investor";
  const manage = membership !== null && canManage(membership.role);
  const [state, setState] = useState<State>({ kind: "loading" });
  const [sort, setSort] = useState<Sort>("newest");
  const [showArchived, setShowArchived] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);

  useEffect(() => {
    if (!activeOrgId) return;
    let cancelled = false;
    async function load() {
      setState({ kind: "loading" });
      setSelected([]);
      try {
        const ideas = await listIdeas(showArchived);
        if (!cancelled) setState({ kind: "ready", ideas });
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
  }, [activeOrgId, showArchived]);

  const ideas = useMemo(
    () => (state.kind === "ready" ? sortIdeas(state.ideas, sort) : []),
    [state, sort],
  );
  const scored = ideas.filter((i) => iqOf(i) !== null);
  const currencies = new Set(scored.map((i) => i.latest_assessment?.currency ?? i.currency));
  const selectedCurrencies = new Set(
    ideas
      .filter((i) => selected.includes(i.id))
      .map((i) => i.latest_assessment?.currency ?? i.currency),
  );

  const header = (
    <PageHeader
      title="Ideas"
      description="Each idea gets an Innovation Quotient out of 100: the AI proposes a score for every dimension, the idea's owner confirms, and the engine does the arithmetic."
      actions={
        canAdd ? (
          <Link href="/ideas/new" className={buttonClass("primary")}>
            Add an idea
          </Link>
        ) : null
      }
    />
  );

  if (!activeOrgId) {
    return (
      <div className="space-y-4">
        {header}
        <Alert tone="info">Choose an organisation in the switcher above.</Alert>
      </div>
    );
  }
  if (state.kind === "loading") return <Loading>Loading ideas...</Loading>;
  if (state.kind === "error") return <Alert tone="error">{state.message}</Alert>;

  function toggle(id: string) {
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  return (
    <div className="space-y-6">
      {header}
      <Card>
        <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
          <div>
            <CardTitle>All ideas</CardTitle>
            <CardDescription>
              {scored.length === 0
                ? "Scored ideas show their IQ and cost per innovation point here."
                : `${scored.length} of ${ideas.length} scored. Tick two or more to compare them side by side.`}
            </CardDescription>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-2 text-[13px] font-medium text-neutral-800">
              Sort
              <select
                aria-label="Sort ideas"
                value={sort}
                onChange={(e) => setSort(e.target.value as Sort)}
                className="h-8 rounded-md border border-neutral-300 bg-white px-2 pr-7 text-[13px] text-neutral-900 shadow-xs focus:outline-2 focus:-outline-offset-1 focus:outline-primary"
              >
                {(Object.keys(SORT_LABELS) as Sort[]).map((key) => (
                  <option key={key} value={key}>
                    {SORT_LABELS[key]}
                  </option>
                ))}
              </select>
            </label>
            {manage && (
              <CheckboxField
                label="Show archived"
                checked={showArchived}
                onChange={(e) => setShowArchived(e.target.checked)}
              />
            )}
          </div>
        </div>

        {sort === "vfm" && currencies.size > 1 && (
          <div className="mt-4">
            <Alert tone="info">
              These ideas use different currencies. Compare Value for Money only between ideas in
              the same currency.
            </Alert>
          </div>
        )}

        {ideas.length === 0 ? (
          <div className="mt-4">
            <EmptyState
              title="No ideas yet."
              action={
                canAdd ? (
                  <Link href="/ideas/new" className={buttonClass("primary")}>
                    Add the first idea
                  </Link>
                ) : null
              }
            >
              {canAdd
                ? "Describe an innovation idea and the AI will propose a score for each of the 12 dimensions."
                : "Ideas added by the team will appear here with their IQ."}
            </EmptyState>
          </div>
        ) : (
          <div className="mt-4">
            <Table
              caption="Ideas with their status, IQ and Value for Money"
              head={
                <>
                  <Th>
                    <span className="sr-only">Compare</span>
                  </Th>
                  <Th>Idea</Th>
                  <Th>Status</Th>
                  <Th className="text-right">IQ</Th>
                  <Th className="text-right">Value for money</Th>
                  <Th>Updated</Th>
                  <Th>
                    <span className="sr-only">Open</span>
                  </Th>
                </>
              }
            >
              {ideas.map((idea) => {
                const latest = idea.latest_assessment;
                const iq = iqOf(idea);
                const vfm = vfmOf(idea);
                const currency = latest?.currency ?? idea.currency;
                return (
                  <tr key={idea.id} className={idea.archived ? "text-neutral-500" : undefined}>
                    <Td>
                      {iq !== null && (
                        <input
                          type="checkbox"
                          aria-label={`Compare ${idea.title}`}
                          checked={selected.includes(idea.id)}
                          onChange={() => toggle(idea.id)}
                          className="h-4 w-4 rounded border-neutral-300 accent-primary"
                        />
                      )}
                    </Td>
                    <Td>
                      <Link
                        href={`/ideas/${idea.id}`}
                        className="font-medium text-neutral-900 hover:underline"
                      >
                        {idea.title}
                      </Link>
                      <span className="block text-xs text-neutral-500">
                        {STAGE_LABELS[idea.stage]}
                        {idea.created_by_name ? ` · ${idea.created_by_name}` : ""}
                        {idea.archived ? " · archived" : ""}
                      </span>
                    </Td>
                    <Td>
                      <Badge tone={IDEA_STATUS_TONES[idea.status]}>
                        {IDEA_STATUS_LABELS[idea.status]}
                      </Badge>
                      {latest && latest.status !== "confirmed" && (
                        <span className="mt-1 block text-xs text-neutral-500">
                          {assessmentLabel(latest.status, latest.proposal_status)}
                        </span>
                      )}
                    </Td>
                    <Td className="text-right tabular-nums">
                      {iq !== null ? (
                        <>
                          <span className="font-medium text-neutral-900">{latest?.iq}</span>
                          <span className="text-neutral-500"> / 100</span>
                        </>
                      ) : (
                        <span className="text-neutral-400">–</span>
                      )}
                    </Td>
                    <Td className="text-right tabular-nums">
                      {vfm !== null && latest?.vfm_per_point ? (
                        <>
                          {formatMoney(latest.vfm_per_point, currency)}
                          <span className="block text-xs text-neutral-500">per point</span>
                        </>
                      ) : iq !== null ? (
                        <span className="text-neutral-500">Not calculable</span>
                      ) : (
                        <span className="text-neutral-400">–</span>
                      )}
                    </Td>
                    <Td className="whitespace-nowrap text-neutral-600">
                      {formatDate(idea.updated_at)}
                    </Td>
                    <Td className="text-right">
                      <Link
                        href={
                          latest && latest.status !== "superseded"
                            ? (assessmentHref(idea) ?? `/ideas/${idea.id}`)
                            : `/ideas/${idea.id}`
                        }
                        className="font-medium text-primary hover:underline"
                      >
                        {latest?.status === "confirmed"
                          ? "See the IQ"
                          : latest?.proposal_status === "ready" && latest.status === "proposed"
                            ? "Review"
                            : "Open"}
                      </Link>
                    </Td>
                  </tr>
                );
              })}
            </Table>
          </div>
        )}

        {selected.length > 0 && (
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Link
              href={`/ideas/compare?ids=${selected.join(",")}`}
              className={buttonClass(selected.length > 1 ? "primary" : "secondary")}
              aria-disabled={selected.length < 2}
              onClick={(e) => {
                if (selected.length < 2) e.preventDefault();
              }}
            >
              Compare {selected.length} {selected.length === 1 ? "idea" : "ideas"}
            </Link>
            {selectedCurrencies.size > 1 && (
              <span className="text-xs text-amber-800">
                Different currencies: Value for Money will not be comparable.
              </span>
            )}
            <Button variant="ghost" size="sm" onClick={() => setSelected([])}>
              Clear
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}
