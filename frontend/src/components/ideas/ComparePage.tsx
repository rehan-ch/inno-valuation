"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, PageHeader } from "@/components/ui/Card";
import { Loading } from "@/components/ui/Loading";
import { Table, Td, Th } from "@/components/ui/Table";
import { ApiError } from "@/lib/api/client";
import { getAssessment, getIdea } from "@/lib/api/ideas";
import type { IdeaOut, IqAssessmentOut } from "@/lib/api/types";
import { formatMoney } from "@/lib/money";

interface Column {
  idea: IdeaOut;
  result: IqAssessmentOut;
}

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; columns: Column[]; skipped: string[] };

interface Row {
  label: string;
  cells: string[];
}

/** The ideas side by side: IQ, Value for Money, category scores and every dimension's final
 * score, each from the idea's latest confirmed assessment. */
export function ComparePage() {
  const params = useSearchParams();
  const ids = (params.get("ids") ?? "").split(",").filter(Boolean);
  const key = ids.join(",");
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const ideas = await Promise.all(ids.map((id) => getIdea(id)));
        const columns: Column[] = [];
        const skipped: string[] = [];
        for (const idea of ideas) {
          const latest = idea.assessments.find((a) => a.status === "confirmed");
          if (!latest) {
            skipped.push(idea.title);
            continue;
          }
          columns.push({ idea, result: await getAssessment(idea.id, latest.id) });
        }
        if (!cancelled) setState({ kind: "ready", columns, skipped });
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
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `ids` is derived from `key`
  }, [key]);

  const header = (
    <PageHeader
      title="Compare ideas"
      description="Each column is an idea's latest confirmed IQ. Value for Money is comparable only between ideas in the same currency."
      actions={
        <Link href="/ideas" className="text-sm font-medium text-primary hover:underline">
          All ideas
        </Link>
      }
    />
  );

  if (ids.length === 0) {
    return (
      <div className="space-y-4">
        {header}
        <Alert tone="info">Tick two or more scored ideas in the list to compare them.</Alert>
      </div>
    );
  }
  if (state.kind === "loading") return <Loading>Loading the comparison...</Loading>;
  if (state.kind === "error") return <Alert tone="error">{state.message}</Alert>;

  const { columns, skipped } = state;
  const currencies = new Set(columns.map((c) => c.result.vfm?.currency ?? c.idea.currency));
  const rows = buildRows(columns);

  function exportCsv() {
    const lines = [
      ["", ...columns.map((c) => c.idea.title)],
      ...rows.map((r) => [r.label, ...r.cells]),
    ].map((cells) => cells.map(csvCell).join(","));
    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "innovaluation-ideas-comparison.csv";
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-6">
      {header}
      {skipped.length > 0 && (
        <Alert tone="info">Not yet scored, so left out: {skipped.join(", ")}.</Alert>
      )}
      {currencies.size > 1 && (
        <Alert tone="info">
          These ideas use different currencies ({[...currencies].join(", ")}). Compare Value for
          Money only between ideas in the same currency.
        </Alert>
      )}
      {columns.length === 0 ? (
        <Alert tone="info">None of the chosen ideas has a confirmed IQ yet.</Alert>
      ) : (
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-neutral-600">
              {columns.length} {columns.length === 1 ? "idea" : "ideas"}, newest scoring of each.
            </p>
            <Button variant="secondary" size="sm" onClick={exportCsv}>
              Export as CSV
            </Button>
          </div>
          <div className="mt-4">
            <Table
              caption="Ideas compared on IQ, Value for Money, categories and dimensions"
              head={
                <>
                  <Th>Measure</Th>
                  {columns.map((c) => (
                    <Th key={c.idea.id} className="text-right">
                      <Link href={`/ideas/${c.idea.id}`} className="text-neutral-900 hover:underline">
                        {c.idea.title}
                      </Link>
                    </Th>
                  ))}
                </>
              }
            >
              {rows.map((row) => (
                <tr key={row.label} className={row.label === "IQ" ? "font-medium" : undefined}>
                  <Td>{row.label}</Td>
                  {row.cells.map((cell, i) => (
                    <Td key={columns[i]?.idea.id ?? i} className="text-right tabular-nums">
                      {cell}
                    </Td>
                  ))}
                </tr>
              ))}
            </Table>
          </div>
        </Card>
      )}
    </div>
  );
}

export function buildRows(columns: Column[]): Row[] {
  const first = columns[0]?.result;
  if (!first) return [];
  const rows: Row[] = [
    { label: "IQ", cells: columns.map((c) => `${c.result.iq} / ${c.result.iq_maximum}`) },
    {
      label: "Value for money (per point)",
      cells: columns.map((c) =>
        c.result.vfm?.per_point
          ? formatMoney(c.result.vfm.per_point, c.result.vfm.currency)
          : "Not calculable",
      ),
    },
    {
      label: "Planned investment",
      cells: columns.map((c) =>
        c.result.vfm?.investment ? formatMoney(c.result.vfm.investment, c.result.vfm.currency) : "–",
      ),
    },
    ...first.categories.map((category, i) => ({
      label: `${category.name} (category IQ)`,
      cells: columns.map((c) => `${c.result.categories[i]?.score ?? "–"} / ${category.maximum}`),
    })),
    ...first.dimensions.map((dimension, i) => ({
      label: `${dimension.order}. ${dimension.name}`,
      cells: columns.map((c) => {
        const d = c.result.dimensions[i];
        const score = d?.final_score ?? d?.proposed_score;
        if (!d || score === undefined || score === null) return "–";
        return `${score} / ${c.result.scale.max}${d.level ? ` · ${d.level.name}` : ""}`;
      }),
    })),
  ];
  return rows;
}

function csvCell(value: string): string {
  return /[",\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}
