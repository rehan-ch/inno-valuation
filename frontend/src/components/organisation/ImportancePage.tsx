"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import { useMe } from "@/components/app/me-context";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import {
  Card,
  CardDescription,
  CardTitle,
  PageHeader,
} from "@/components/ui/Card";
import { TextField } from "@/components/ui/fields";
import { Loading } from "@/components/ui/Loading";
import { Table, Td, Th } from "@/components/ui/Table";
import { ApiError } from "@/lib/api/client";
import type { WeightOut, WeightsChangeOut, WeightsOut } from "@/lib/api/types";
import {
  getWeights,
  getWeightsHistory,
  resetWeights,
  setWeights,
} from "@/lib/api/weights";
import { formatDateTime } from "@/lib/format";
import { useSubmit } from "@/lib/forms";

const CATEGORY_LABELS: Record<string, string> = {
  customer_facing: "Customer-Facing",
  process: "Process",
  strategic: "Strategic",
};

type Limits = WeightsOut["limits"];

/** Why a typed weight is not allowed, or undefined when it is (mirrors the engine's limits). */
export function weightError(value: string, limits: Limits): string | undefined {
  const text = value.trim();
  if (!/^\d+(\.\d+)?$/.test(text)) return "Enter a number, e.g. 1 or 2.5.";
  const decimals = text.split(".")[1]?.replace(/0+$/, "") ?? "";
  if (decimals.length > limits.max_decimal_places) {
    return `At most ${limits.max_decimal_places} decimal places.`;
  }
  const number = Number(text);
  if (number < limits.minimum || number > limits.maximum) {
    return `From ${limits.minimum} to ${limits.maximum}.`;
  }
  return undefined;
}

/** "Data Intelligence 3, Customer Journey 2.5" for the weights that differ from 1. */
export function describeChange(
  change: WeightsChangeOut,
  names: Map<string, string>,
): string {
  if (!change.custom) return "Every dimension counts equally.";
  const raised = Object.entries(change.weights)
    .filter(([, weight]) => Number(weight) !== 1)
    .map(([key, weight]) => `${names.get(key) ?? key} ${weight}`);
  return raised.join(", ");
}

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; weights: WeightsOut; history: WeightsChangeOut[] };

/** Which dimensions matter more to the company (P4.08). Importance never changes a score or
 * the IQ; it only orders tied priorities. */
export function ImportancePage() {
  const { me } = useMe();
  const activeOrgId = me.active_organisation_id;
  const [state, setState] = useState<State>({ kind: "loading" });
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!activeOrgId) return;
    let cancelled = false;
    async function load() {
      setState({ kind: "loading" });
      setNotice(null);
      try {
        const [weights, history] = await Promise.all([
          getWeights(),
          getWeightsHistory(),
        ]);
        if (!cancelled) setState({ kind: "ready", weights, history });
      } catch (err) {
        if (!cancelled) {
          setState({
            kind: "error",
            message:
              err instanceof ApiError ? err.message : "Something went wrong.",
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
        <PageHeader title="Dimension importance" />
        <Alert tone="info">
          Choose an organisation in the switcher above, or{" "}
          <Link
            href="/organisations/new"
            className="font-medium text-primary hover:underline"
          >
            create one
          </Link>
          .
        </Alert>
      </div>
    );
  }

  if (state.kind === "loading")
    return <Loading>Loading the dimension importance...</Loading>;
  if (state.kind === "error")
    return <Alert tone="error">{state.message}</Alert>;

  const { weights, history } = state;
  const names = new Map(weights.weights.map((w) => [w.key, w.name]));

  async function reload(saved: WeightsOut, message: string) {
    const fresh = await getWeightsHistory().catch(() => history);
    setState({ kind: "ready", weights: saved, history: fresh });
    setNotice(message);
  }

  return (
    <div className="max-w-3xl space-y-6">
      <PageHeader
        title="Dimension importance"
        description="Which of the 12 dimensions matter more to your company."
      />
      <Alert tone="info">
        Importance never changes a score or the IQ. It only decides the order of
        the &ldquo;Focus first&rdquo; list for an idea when two dimensions have
        the same score: the more important one comes first. Every dimension
        starts at 1.
      </Alert>
      <div className="flex flex-wrap items-center gap-3 text-sm text-neutral-600">
        {weights.custom ? (
          <Badge tone="blue">Custom importance is active</Badge>
        ) : (
          <Badge tone="neutral">Every dimension counts equally</Badge>
        )}
        {weights.set_at && (
          <span>
            Last changed {formatDateTime(weights.set_at)}
            {weights.set_by_name ? ` by ${weights.set_by_name}` : ""}.
          </span>
        )}
      </div>
      {notice && <Alert tone="success">{notice}</Alert>}
      <WeightsForm
        // Seeded from the weights once; a save or a switch gives a fresh form.
        key={`${activeOrgId}:${weights.set_at ?? "default"}`}
        weights={weights}
        onSaved={(saved, message) => {
          setNotice(null);
          void reload(saved, message);
        }}
      />
      <Card>
        <CardTitle>History</CardTitle>
        <CardDescription>
          Every change to the importance, newest first.
        </CardDescription>
        {history.length === 0 ? (
          <p className="mt-3 text-sm text-neutral-600">No changes yet.</p>
        ) : (
          <ul className="mt-3 divide-y divide-neutral-100">
            {history.map((change) => (
              <li
                key={change.id}
                className="py-2.5 text-sm first:pt-0 last:pb-0"
              >
                <p className="text-neutral-900">
                  {describeChange(change, names)}
                </p>
                <p className="mt-0.5 text-xs text-neutral-500">
                  {formatDateTime(change.set_at)}
                  {change.set_by_name ? ` by ${change.set_by_name}` : ""}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

function WeightsForm({
  weights,
  onSaved,
}: {
  weights: WeightsOut;
  onSaved: (saved: WeightsOut, message: string) => void;
}) {
  const { busy, error, run } = useSubmit();
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(weights.weights.map((w) => [w.key, w.weight])),
  );
  const [errors, setErrors] = useState<Record<string, string | undefined>>({});
  const editable = weights.can_change;

  function validate(): boolean {
    const found: Record<string, string | undefined> = {};
    for (const w of weights.weights) {
      found[w.key] = weightError(values[w.key] ?? "", weights.limits);
    }
    // PROVISIONAL: see open-questions Q22. The server enforces the same rule (422).
    const allZero = weights.weights.every((w) => Number(values[w.key]) === 0);
    if (allZero && !Object.values(found).some(Boolean)) {
      const first = weights.weights[0];
      if (first) found[first.key] = "At least one dimension must be above 0.";
    }
    setErrors(found);
    return !Object.values(found).some(Boolean);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!validate()) return;
    const result = await run(() =>
      setWeights({
        weights: Object.fromEntries(
          weights.weights.map((w) => [w.key, (values[w.key] ?? "").trim()]),
        ),
      }),
    );
    if (result) onSaved(result, "Saved.");
  }

  async function handleReset() {
    const result = await run(resetWeights);
    if (result) onSaved(result, "Every dimension counts equally again.");
  }

  return (
    <Card>
      <CardTitle>Importance per dimension</CardTitle>
      <CardDescription>
        {editable
          ? `A number from ${weights.limits.minimum} to ${weights.limits.maximum}. Higher means more important; the numbers need not add up to anything.`
          : "Only an owner or admin can change the importance."}
      </CardDescription>
      <form
        onSubmit={(e) => void handleSubmit(e)}
        className="mt-4 space-y-4"
        noValidate
      >
        {error && <Alert tone="error">{error.message}</Alert>}
        <Table
          caption="Importance per dimension"
          head={
            <>
              <Th>Dimension</Th>
              <Th>Group</Th>
              <Th className="w-36">Importance</Th>
            </>
          }
        >
          {weights.weights.map((w: WeightOut) => (
            <tr key={w.key}>
              <Td>
                <span className="mr-2 text-neutral-400 tabular-nums">
                  {w.order}.
                </span>
                <span className="font-medium text-neutral-900">{w.name}</span>
              </Td>
              <Td>{CATEGORY_LABELS[w.category] ?? w.category}</Td>
              <Td>
                <TextField
                  label={`${w.name} importance`}
                  labelHidden
                  compact
                  inputMode="decimal"
                  name={`weight-${w.key}`}
                  disabled={!editable}
                  error={errors[w.key]}
                  value={values[w.key] ?? ""}
                  onChange={(e) => {
                    setValues((prev) => ({ ...prev, [w.key]: e.target.value }));
                    setErrors((prev) => ({ ...prev, [w.key]: undefined }));
                  }}
                />
              </Td>
            </tr>
          ))}
        </Table>
        {editable && (
          <div className="flex flex-wrap justify-end gap-3 border-t border-neutral-200 pt-4">
            <Button
              type="button"
              variant="secondary"
              disabled={busy || !weights.custom}
              onClick={() => void handleReset()}
            >
              Reset to equal importance
            </Button>
            <Button type="submit" busy={busy}>
              Save importance
            </Button>
          </div>
        )}
      </form>
    </Card>
  );
}
