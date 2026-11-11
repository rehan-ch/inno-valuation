"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";

import { useMe } from "@/components/app/me-context";
import { gapWords } from "@/components/compass/Compass";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader, PageHeader } from "@/components/ui/Card";
import { TextField } from "@/components/ui/fields";
import { Loading } from "@/components/ui/Loading";
import { Table, Td, Th } from "@/components/ui/Table";
import { ApiError } from "@/lib/api/client";
import { dimensionHref, getDashboard } from "@/lib/api/insights";
import { getTargets, getTargetsHistory, setTargets } from "@/lib/api/targets";
import type {
  CompassOut,
  DashboardOut,
  TargetScaleOut,
  TargetsChangeOut,
  TargetsOut,
} from "@/lib/api/types";
import { formatDateTime } from "@/lib/format";
import { useSubmit } from "@/lib/forms";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; targets: TargetsOut; history: TargetsChangeOut[]; dashboard: DashboardOut };

/** Why a typed target is not allowed, or undefined when it is. Blank means no target.
 * The range is the scale's own, sent by the server. */
export function targetError(value: string, scale: Pick<TargetScaleOut, "minimum" | "maximum">): string | undefined {
  const text = value.trim();
  if (!text) return undefined;
  if (!/^\d+$/.test(text)) return "A whole number.";
  const number = Number(text);
  if (number < scale.minimum || number > scale.maximum) {
    return `From ${scale.minimum} to ${scale.maximum}.`;
  }
  return undefined;
}

const SCALE_WORDS = { readiness: "Readiness", iq: "Idea (IQ)" } as const;

/** The scores the organisation wants to reach, per dimension, on each of the two scales
 * (P5.06). A target changes no score. The gap shown is the server's: target minus the
 * current score. */
export function TargetsPage() {
  const { me } = useMe();
  const activeOrgId = me.active_organisation_id;
  const [state, setState] = useState<State>({ kind: "loading" });
  const [notice, setNotice] = useState<string | null>(null);
  // The organisation the page is showing, so a save that finishes after a switch is dropped.
  const showing = useRef(activeOrgId);

  useEffect(() => {
    if (!activeOrgId) return;
    let cancelled = false;
    showing.current = activeOrgId;
    async function load() {
      setState({ kind: "loading" });
      setNotice(null);
      try {
        const [targets, history, dashboard] = await Promise.all([
          getTargets(),
          getTargetsHistory(),
          getDashboard(),
        ]);
        if (!cancelled) setState({ kind: "ready", targets, history, dashboard });
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
        <PageHeader title="Targets" />
        <Alert tone="info">
          Choose an organisation in the switcher above, or{" "}
          <Link href="/organisations/new" className="font-medium text-primary hover:underline">
            create one
          </Link>
          .
        </Alert>
      </div>
    );
  }
  if (state.kind === "loading") return <Loading>Loading the targets...</Loading>;
  if (state.kind === "error") return <Alert tone="error">{state.message}</Alert>;

  const { targets, dashboard, history: allHistory } = state;
  // Idea targets are hidden without the AI, and so are their earlier changes.
  const history = me.ai_enabled ? allHistory : allHistory.filter((c) => c.scale !== "iq");
  const names = new Map(targets.readiness.targets.map((t) => [t.key, t.name]));

  /** After a save: the new targets, and the gaps and history the server now reports. */
  async function saved(next: TargetsOut, message: string) {
    const savedFor = activeOrgId;
    const [freshHistory, freshDashboard] = await Promise.all([
      getTargetsHistory().catch(() => allHistory),
      getDashboard(dashboard.iq?.idea_id).catch(() => dashboard),
    ]);
    if (showing.current !== savedFor) return;
    setState({ kind: "ready", targets: next, history: freshHistory, dashboard: freshDashboard });
    setNotice(message);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Targets"
        description="The score you want to reach on each dimension. A target never changes a score; it shows the gap between where you are and where you want to be."
      />
      {notice && <Alert tone="success">{notice}</Alert>}
      {!targets.can_change && (
        <Alert tone="info">Owners and admins set the targets. You can see them here.</Alert>
      )}

      <div
        className={`grid grid-cols-1 items-start gap-6${me.ai_enabled ? " xl:grid-cols-2" : ""}`}
      >
        <ScaleForm
          key={`readiness-${targets.readiness.set_at ?? "none"}`}
          title="Readiness targets"
          description={`For the whole organisation. Each dimension scores ${targets.readiness.minimum} to ${targets.readiness.maximum}.`}
          scale={targets.readiness}
          canChange={targets.can_change}
          compass={dashboard.readiness?.compass ?? null}
          currentLabel="Latest result"
          emptyCurrent="No final readiness result yet."
          onSaved={(next) => saved(next, "Readiness targets saved.")}
        />
        {me.ai_enabled && (
          <ScaleForm
            key={`iq-${targets.iq.set_at ?? "none"}`}
            title="Idea targets"
            description={`What you want every idea to reach. Each dimension scores ${targets.iq.minimum} to ${targets.iq.maximum}.${
              dashboard.iq ? ` Shown against "${dashboard.iq.idea_title}", the idea scored last.` : ""
            }`}
            scale={targets.iq}
            canChange={targets.can_change}
            compass={dashboard.iq?.compass ?? null}
            currentLabel="Latest idea"
            emptyCurrent="No idea has confirmed scores yet."
            onSaved={(next) => saved(next, "Idea targets saved.")}
          />
        )}
      </div>

      <Card>
        <CardHeader
          title="Earlier targets"
          description="Every change is kept, newest first."
        />
        <div className="mt-4">
          {history.length === 0 ? (
            <p className="text-sm text-neutral-600">No targets have been set yet.</p>
          ) : (
            <Table
              caption="Changes of the targets"
              head={
                <>
                  <Th>When</Th>
                  <Th>Who</Th>
                  <Th>Scale</Th>
                  <Th>Targets after the change</Th>
                </>
              }
            >
              {history.map((change) => (
                <tr key={change.id}>
                  <Td className="whitespace-nowrap">{formatDateTime(change.set_at)}</Td>
                  <Td>{change.set_by_name ?? "Someone who has left"}</Td>
                  <Td>{SCALE_WORDS[change.scale]}</Td>
                  <Td>{describeTargets(change, names)}</Td>
                </tr>
              ))}
            </Table>
          )}
        </div>
      </Card>
    </div>
  );
}

/** "Customer Journey 20, Data Intelligence 25", or that every target was removed. */
export function describeTargets(change: TargetsChangeOut, names: Map<string, string>): string {
  const entries = Object.entries(change.targets);
  if (entries.length === 0) return "Every target removed.";
  return entries.map(([key, value]) => `${names.get(key) ?? key} ${value}`).join(", ");
}

function ScaleForm({
  title,
  description,
  scale,
  canChange,
  compass,
  currentLabel,
  emptyCurrent,
  onSaved,
}: {
  title: string;
  description: string;
  scale: TargetScaleOut;
  canChange: boolean;
  compass: CompassOut | null;
  currentLabel: string;
  emptyCurrent: string;
  onSaved: (next: TargetsOut) => Promise<void>;
}) {
  const initial = Object.fromEntries(
    scale.targets.map((t) => [t.key, t.target === null ? "" : String(t.target)]),
  );
  const [values, setValues] = useState<Record<string, string>>(initial);
  const { busy, error, run } = useSubmit();
  const errors = Object.fromEntries(
    scale.targets.map((t) => [t.key, targetError(values[t.key] ?? "", scale)]),
  );
  const invalid = Object.values(errors).some(Boolean);
  // Compared as numbers, so "08" is not a change from 8.
  const asTarget = (text: string) => (text.trim() === "" ? null : Number(text));
  const dirty = scale.targets.some(
    (t) => asTarget(values[t.key] ?? "") !== asTarget(initial[t.key] ?? ""),
  );
  const current = new Map(compass?.segments.map((s) => [s.key, s]) ?? []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (invalid) return;
    await run(async () => {
      const targets: Record<string, number | null> = {};
      for (const t of scale.targets) {
        const text = (values[t.key] ?? "").trim();
        targets[t.key] = text ? Number(text) : null;
      }
      await onSaved(await setTargets(scale.scale, targets));
    });
  }

  return (
    <Card>
      <form onSubmit={(event) => void submit(event)} noValidate>
        <CardHeader title={title} description={description} />
        {error && (
          <div className="mt-3">
            <Alert tone="error">{error.message}</Alert>
          </div>
        )}
        <div className="mt-4">
          <Table
            caption={title}
            head={
              <>
                <Th>Dimension</Th>
                <Th className="text-right">{currentLabel}</Th>
                <Th>Target</Th>
                <Th>Gap</Th>
              </>
            }
          >
            {scale.targets.map((target) => {
              const segment = current.get(target.key);
              return (
                <tr key={target.key}>
                  <Td>
                    <Link
                      href={dimensionHref(target.key)}
                      className="text-neutral-900 hover:text-primary hover:underline"
                    >
                      <span className="mr-2 text-neutral-400 tabular-nums">{target.order}</span>
                      {target.name}
                    </Link>
                  </Td>
                  <Td className="text-right whitespace-nowrap tabular-nums">
                    {segment ? (
                      <>
                        {segment.score}
                        <span className="text-neutral-500"> / {segment.maximum}</span>
                      </>
                    ) : (
                      "–"
                    )}
                  </Td>
                  <Td>
                    {canChange ? (
                      <div className="w-20">
                        <TextField
                          label={`Target for ${target.name}`}
                          labelHidden
                          compact
                          inputMode="numeric"
                          placeholder="–"
                          value={values[target.key] ?? ""}
                          error={errors[target.key]}
                          onChange={(event) =>
                            setValues((v) => ({ ...v, [target.key]: event.target.value }))
                          }
                        />
                      </div>
                    ) : (
                      <span className="tabular-nums">{target.target ?? "–"}</span>
                    )}
                  </Td>
                  <Td className="whitespace-nowrap text-neutral-600">
                    {segment && segment.gap !== null ? gapWords(segment.gap) : "–"}
                  </Td>
                </tr>
              );
            })}
          </Table>
        </div>
        {!compass && <p className="mt-3 text-xs text-neutral-500">{emptyCurrent}</p>}
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-neutral-500">
            {scale.set_at
              ? `Last changed ${formatDateTime(scale.set_at)}${scale.set_by_name ? ` by ${scale.set_by_name}` : ""}.`
              : "No targets set yet."}{" "}
            {canChange && "Leave a box empty for no target. The gap updates when you save."}
          </p>
          {canChange && (
            <Button type="submit" busy={busy} disabled={!dirty || invalid}>
              Save targets
            </Button>
          )}
        </div>
      </form>
    </Card>
  );
}
