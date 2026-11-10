"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";

import { useMe } from "@/components/app/me-context";
import { gapWords } from "@/components/compass/Compass";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader, PageHeader } from "@/components/ui/Card";
import { Change, changeText } from "@/components/ui/Change";
import { EmptyState } from "@/components/ui/EmptyState";
import { SelectField } from "@/components/ui/fields";
import { Loading } from "@/components/ui/Loading";
import { Table, Td, Th } from "@/components/ui/Table";
import { ApiError } from "@/lib/api/client";
import {
  dimensionHref,
  getDashboard,
  getIdeaHistory,
  getReadinessHistory,
} from "@/lib/api/insights";
import type {
  Direction,
  HistoryDimensionOut,
  IdeaChoiceOut,
  IdeaHistoryOut,
  ReadinessHistoryOut,
} from "@/lib/api/types";
import { downloadCsv } from "@/lib/csv";
import { formatDate } from "@/lib/format";
import { formatMoney } from "@/lib/money";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | {
      kind: "ready";
      readiness: ReadinessHistoryOut;
      ideas: IdeaChoiceOut[];
      idea: IdeaHistoryOut | null;
    };

/** One result in a comparison: a column of the table. */
interface Column {
  id: string;
  href: string;
  date: string;
  version: number;
  compared: boolean;
  headline: ReactNode;
  headlineText: string;
  change: { change: number | string | null; direction: Direction | null };
  extra: { label: string; cells: ReactNode; text: string }[];
  dimensions: HistoryDimensionOut[];
}

/** How results changed over time (P5.07): every final readiness result, and every
 * confirmed assessment of one idea, each beside the one before it. The changes are the
 * server's, and only between results on the same question set version. Readiness and
 * ideas are separate tables; they are never put on one scale. */
export function HistoryPage() {
  const { me } = useMe();
  const activeOrgId = me.active_organisation_id;
  const params = useSearchParams();
  const router = useRouter();
  const ideaParam = params.get("idea");
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    if (!activeOrgId) return;
    let cancelled = false;
    async function load() {
      try {
        const [readiness, dashboard] = await Promise.all([getReadinessHistory(), getDashboard()]);
        const chosen =
          dashboard.ideas.find((i) => i.idea_id === ideaParam)?.idea_id ??
          dashboard.ideas[0]?.idea_id ??
          null;
        const idea = chosen ? await getIdeaHistory(chosen) : null;
        if (!cancelled) setState({ kind: "ready", readiness, ideas: dashboard.ideas, idea });
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
  }, [activeOrgId, ideaParam]);

  if (!activeOrgId) {
    return (
      <div className="space-y-4">
        <PageHeader title="History" />
        <Alert tone="info">Choose an organisation in the switcher above.</Alert>
      </div>
    );
  }
  if (state.kind === "loading") return <Loading>Loading the history...</Loading>;
  if (state.kind === "error") return <Alert tone="error">{state.message}</Alert>;

  const { readiness, ideas, idea } = state;

  const readinessColumns: Column[] = readiness.entries.map((entry) => ({
    id: entry.assessment_id,
    href: `/readiness/${entry.assessment_id}/result`,
    date: entry.finalised_at,
    version: entry.question_set_version,
    compared: entry.compared_with !== null,
    headline: (
      <>
        {entry.total}
        <span className="font-normal text-neutral-500"> / {entry.total_maximum}</span>
      </>
    ),
    headlineText: `${entry.total} / ${entry.total_maximum}`,
    change: { change: entry.total_change, direction: entry.total_direction },
    extra: [{ label: "Band", cells: entry.band_name, text: entry.band_name }],
    dimensions: entry.dimensions,
  }));

  const ideaColumns: Column[] = (idea?.entries ?? []).map((entry) => {
    const vfm = entry.vfm?.per_point
      ? formatMoney(entry.vfm.per_point, entry.vfm.currency)
      : "Not calculable";
    return {
      id: entry.assessment_id,
      href: `/ideas/${idea?.idea_id}/assessments/${entry.assessment_id}`,
      date: entry.confirmed_at,
      version: entry.question_set_version,
      compared: entry.compared_with !== null,
      headline: (
        <>
          {entry.iq}
          <span className="font-normal text-neutral-500"> / {entry.iq_maximum}</span>
        </>
      ),
      headlineText: `${entry.iq} / ${entry.iq_maximum}`,
      change: { change: entry.iq_change, direction: entry.iq_direction },
      extra: [
        {
          label: "Value for money (per point, lower is better)",
          cells: (
            <>
              {vfm}
              <span className="ml-2 font-normal">
                <Change change={entry.vfm_change} direction={entry.vfm_direction} />
              </span>
            </>
          ),
          text: `${vfm}${entry.vfm_change ? ` (${changeText(entry.vfm_change, entry.vfm_direction)})` : ""}`,
        },
        {
          label: "Planned investment",
          cells: entry.vfm?.investment
            ? formatMoney(entry.vfm.investment, entry.vfm.currency)
            : "–",
          text: entry.vfm?.investment ? formatMoney(entry.vfm.investment, entry.vfm.currency) : "",
        },
      ],
      dimensions: entry.dimensions,
    };
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="History"
        description="How your results changed from one assessment to the next. An earlier result is never overwritten; open any of them as it was."
      />

      <Card>
        <CardHeader
          title="Readiness over time"
          description="Every final readiness result, newest first."
          actions={
            readinessColumns.length > 0 ? (
              <Button
                variant="secondary"
                size="sm"
                onClick={() =>
                  downloadCsv(
                    "innovaluation-readiness-history.csv",
                    csvRows("Readiness score", readinessColumns),
                  )
                }
              >
                Export as CSV
              </Button>
            ) : null
          }
        />
        <div className="mt-4">
          {readinessColumns.length === 0 ? (
            <EmptyState title="No final readiness result yet">
              Once the team&apos;s answers are agreed and made final, the result appears here.
              Run the assessment again later to see what changed.
            </EmptyState>
          ) : (
            <Comparison
              caption="Readiness results over time"
              headlineLabel="Readiness score"
              columns={readinessColumns}
            />
          )}
        </div>
      </Card>

      <Card>
        <CardHeader
          title="An idea over time"
          description={
            idea
              ? `Every confirmed scoring of "${idea.idea_title}", newest first.`
              : "Every confirmed scoring of one idea."
          }
          actions={
            <>
              {ideas.length > 1 && idea && (
                <div className="w-52">
                  <SelectField
                    label="Idea"
                    labelHidden
                    compact
                    value={idea.idea_id}
                    onChange={(event) => router.replace(`/history?idea=${event.target.value}`)}
                  >
                    {ideas.map((choice) => (
                      <option key={choice.idea_id} value={choice.idea_id}>
                        {choice.title}
                      </option>
                    ))}
                  </SelectField>
                </div>
              )}
              {ideaColumns.length > 0 && (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() =>
                    downloadCsv("innovaluation-idea-history.csv", csvRows("IQ", ideaColumns))
                  }
                >
                  Export as CSV
                </Button>
              )}
            </>
          }
        />
        <div className="mt-4">
          {ideaColumns.length === 0 ? (
            <EmptyState title="No idea has confirmed scores yet">
              Once an idea&apos;s scores are confirmed, its IQ appears here. Score it again
              later to see what changed.
            </EmptyState>
          ) : (
            <Comparison caption="Scorings of the idea over time" headlineLabel="IQ" columns={ideaColumns} />
          )}
        </div>
      </Card>
    </div>
  );
}

function Comparison({
  caption,
  headlineLabel,
  columns,
}: {
  caption: string;
  headlineLabel: string;
  columns: Column[];
}) {
  const first = columns[0];
  if (!first) return null;
  const hasTargets = first.dimensions.some((d) => d.target !== null);
  return (
    <>
      <Table
        caption={caption}
        head={
          <>
            <Th>Measure</Th>
            {columns.map((column, i) => (
              <Th key={column.id} className="text-right">
                <Link href={column.href} className="text-neutral-900 hover:underline">
                  {formatDate(column.date)}
                </Link>
                {i === 0 && <span className="ml-1.5 font-normal text-neutral-500">latest</span>}
              </Th>
            ))}
            {hasTargets && <Th className="text-right">Target</Th>}
            {hasTargets && <Th>Gap now</Th>}
          </>
        }
      >
        <tr className="font-medium">
          <Td>{headlineLabel}</Td>
          {columns.map((column) => (
            <Td key={column.id} className="text-right">
              <span className="tabular-nums">{column.headline}</span>
              <span className="mt-0.5 block text-xs font-normal">
                <Change change={column.change.change} direction={column.change.direction} />
              </span>
            </Td>
          ))}
          {hasTargets && <Td />}
          {hasTargets && <Td />}
        </tr>
        {first.extra.map((row, rowIndex) => (
          <tr key={row.label}>
            <Td>{row.label}</Td>
            {columns.map((column) => (
              <Td key={column.id} className="text-right tabular-nums">
                {column.extra[rowIndex]?.cells}
              </Td>
            ))}
            {hasTargets && <Td />}
            {hasTargets && <Td />}
          </tr>
        ))}
        {first.dimensions.map((dimension, rowIndex) => (
          <tr key={dimension.key}>
            <Td>
              <Link
                href={dimensionHref(dimension.key)}
                className="text-neutral-900 hover:text-primary hover:underline"
              >
                <span className="mr-2 text-neutral-400 tabular-nums">{dimension.order}</span>
                {dimension.name}
              </Link>
            </Td>
            {columns.map((column) => {
              const cell = column.dimensions[rowIndex];
              if (!cell) return <Td key={column.id} />;
              return (
                <Td key={column.id} className="text-right">
                  <span className="tabular-nums">
                    {cell.score}
                    <span className="text-neutral-500"> / {cell.maximum}</span>
                  </span>
                  <span className="mt-0.5 block text-xs">
                    <Change change={cell.change} direction={cell.direction} />
                  </span>
                </Td>
              );
            })}
            {hasTargets && (
              <Td className="text-right tabular-nums">{dimension.target ?? "–"}</Td>
            )}
            {hasTargets && (
              <Td className="whitespace-nowrap text-neutral-600">
                {dimension.gap !== null ? gapWords(dimension.gap) : "–"}
              </Td>
            )}
          </tr>
        ))}
      </Table>
      <p className="mt-3 text-xs text-neutral-500">
        Each change is from the result before it.
        {columns.some((c) => !c.compared) &&
          " The first result, and a result on another question set version, has nothing to be compared with."}
        {hasTargets && " Targets are the ones set today; the gap is for the latest result."}
      </p>
    </>
  );
}

/** The comparison as rows of text, one column per result, for the CSV file. */
export function csvRows(headlineLabel: string, columns: Column[]): string[][] {
  const first = columns[0];
  if (!first) return [];
  const withChange = (value: string, change: string) => (change ? `${value} (${change})` : value);
  return [
    ["Measure", ...columns.map((c) => formatDate(c.date))],
    ["Question set version", ...columns.map((c) => String(c.version))],
    [
      headlineLabel,
      ...columns.map((c) =>
        withChange(c.headlineText, changeText(c.change.change, c.change.direction)),
      ),
    ],
    ...first.extra.map((row, i) => [row.label, ...columns.map((c) => c.extra[i]?.text ?? "")]),
    ...first.dimensions.map((dimension, i) => [
      `${dimension.order}. ${dimension.name}`,
      ...columns.map((c) => {
        const cell = c.dimensions[i];
        if (!cell) return "";
        return withChange(`${cell.score} / ${cell.maximum}`, changeText(cell.change, cell.direction));
      }),
    ]),
  ];
}
