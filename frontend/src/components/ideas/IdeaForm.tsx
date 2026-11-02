"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import { useMe } from "@/components/app/me-context";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardDescription, CardTitle, PageHeader } from "@/components/ui/Card";
import { CurrencySelect } from "@/components/ui/CurrencySelect";
import { SelectField, TextAreaField, TextField } from "@/components/ui/fields";
import { Loading } from "@/components/ui/Loading";
import { ApiError } from "@/lib/api/client";
import { createIdea, getIdea, updateIdea } from "@/lib/api/ideas";
import { getOrganisation } from "@/lib/api/organisation";
import type { IdeaOut, IdeaStage } from "@/lib/api/types";
import { useSubmit } from "@/lib/forms";
import { moneyError } from "@/lib/money";

import { STAGE_LABELS, STAGES } from "./status";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; idea: IdeaOut | null; currency: string };

interface Values {
  title: string;
  summary: string;
  problem: string;
  target_market: string;
  uniqueness: string;
  team: string;
  risks: string;
  stage: IdeaStage;
  currency: string;
  investment: string;
  expected_value: string;
}

function initial(idea: IdeaOut | null, currency: string): Values {
  return {
    title: idea?.title ?? "",
    summary: idea?.summary ?? "",
    problem: idea?.problem ?? "",
    target_market: idea?.target_market ?? "",
    uniqueness: idea?.uniqueness ?? "",
    team: idea?.team ?? "",
    risks: idea?.risks ?? "",
    stage: idea?.stage ?? "idea",
    currency: idea?.currency ?? currency,
    investment: idea?.investment ?? "",
    expected_value: idea?.expected_value ?? "",
  };
}

/** Add an idea, or edit one (``ideaId`` given). The AI reads these words to propose the
 * scores, so the form asks for the facts a reviewer would want. */
export function IdeaForm({ ideaId }: { ideaId?: string }) {
  const { me } = useMe();
  const activeOrgId = me.active_organisation_id;
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    if (!activeOrgId) return;
    let cancelled = false;
    async function load() {
      try {
        const [org, idea] = await Promise.all([
          getOrganisation(),
          ideaId ? getIdea(ideaId) : Promise.resolve(null),
        ]);
        if (!cancelled) setState({ kind: "ready", idea, currency: org.currency });
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
  }, [activeOrgId, ideaId]);

  if (!activeOrgId) return <Alert tone="info">Choose an organisation in the switcher above.</Alert>;
  if (state.kind === "loading") return <Loading>Loading...</Loading>;
  if (state.kind === "error") return <Alert tone="error">{state.message}</Alert>;

  if (state.idea && !state.idea.can_change) {
    return (
      <div className="space-y-4">
        <PageHeader title={state.idea.title} />
        <Alert tone="info">Only the person who added this idea, or an owner or admin, can edit it.</Alert>
      </div>
    );
  }
  if (state.idea && state.idea.status === "submitted") {
    return (
      <div className="space-y-4">
        <PageHeader title={state.idea.title} />
        <Alert tone="info">
          This idea is being scored. Confirm or replace the proposal first, then edit it.{" "}
          <Link href={`/ideas/${state.idea.id}`} className="font-medium text-primary hover:underline">
            Back to the idea
          </Link>
        </Alert>
      </div>
    );
  }

  return (
    <div className="max-w-2xl space-y-6">
      <PageHeader
        title={state.idea ? "Edit idea" : "New idea"}
        description={
          state.idea
            ? "Changes apply to the next scoring; a confirmed IQ stays as it was."
            : "Describe the idea in plain words. The AI reads exactly this text when it proposes the scores."
        }
      />
      <Form key={state.idea?.id ?? "new"} idea={state.idea} currency={state.currency} />
    </div>
  );
}

function Form({ idea, currency }: { idea: IdeaOut | null; currency: string }) {
  const router = useRouter();
  const { busy, error, run } = useSubmit();
  const [values, setValues] = useState<Values>(() => initial(idea, currency));
  const [errors, setErrors] = useState<Partial<Record<keyof Values, string>>>({});

  function set<K extends keyof Values>(field: K, value: Values[K]) {
    setValues((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: undefined }));
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const found: Partial<Record<keyof Values, string>> = {};
    if (!values.title.trim()) found.title = "Give the idea a title.";
    if (!values.summary.trim()) found.summary = "Describe the idea in a few sentences.";
    const investment = moneyError(values.investment, values.currency);
    if (investment) found.investment = investment;
    const expected = moneyError(values.expected_value, values.currency);
    if (expected) found.expected_value = expected;
    if (Object.keys(found).length > 0) {
      setErrors(found);
      return;
    }
    const body = {
      title: values.title,
      summary: values.summary,
      problem: values.problem || null,
      target_market: values.target_market || null,
      uniqueness: values.uniqueness || null,
      team: values.team || null,
      risks: values.risks || null,
      stage: values.stage,
      currency: values.currency,
      investment: values.investment.trim() || null,
      expected_value: values.expected_value.trim() || null,
    };
    const saved = await run(() => (idea ? updateIdea(idea.id, body) : createIdea(body)));
    if (saved) router.push(`/ideas/${saved.id}`);
  }

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="space-y-6" noValidate>
      {error && <Alert tone="error">{error.message}</Alert>}
      <Card>
        <CardTitle>The idea</CardTitle>
        <CardDescription>
          What it is, the problem it solves and who it is for. Facts and examples help the
          scoring more than claims.
        </CardDescription>
        <div className="mt-4 space-y-4">
          <TextField
            label="Title"
            name="title"
            required
            maxLength={200}
            error={errors.title}
            value={values.title}
            onChange={(e) => set("title", e.target.value)}
          />
          <TextAreaField
            label="Summary"
            name="summary"
            required
            rows={4}
            hint="A few sentences on what the idea is and what it changes."
            error={errors.summary}
            value={values.summary}
            onChange={(e) => set("summary", e.target.value)}
          />
          <TextAreaField
            label="Problem or opportunity"
            name="problem"
            value={values.problem}
            onChange={(e) => set("problem", e.target.value)}
          />
          <TextAreaField
            label="Target market"
            name="target_market"
            hint="Who buys or uses it, and how many of them there are."
            value={values.target_market}
            onChange={(e) => set("target_market", e.target.value)}
          />
          <TextAreaField
            label="What makes it different"
            name="uniqueness"
            value={values.uniqueness}
            onChange={(e) => set("uniqueness", e.target.value)}
          />
          <TextAreaField
            label="Team"
            name="team"
            value={values.team}
            onChange={(e) => set("team", e.target.value)}
          />
          <TextAreaField
            label="Risks"
            name="risks"
            value={values.risks}
            onChange={(e) => set("risks", e.target.value)}
          />
          <SelectField
            label="Stage"
            name="stage"
            value={values.stage}
            onChange={(e) => set("stage", e.target.value as IdeaStage)}
          >
            {STAGES.map((stage) => (
              <option key={stage} value={stage}>
                {STAGE_LABELS[stage]}
              </option>
            ))}
          </SelectField>
        </div>
      </Card>

      <Card>
        <CardTitle>Investment</CardTitle>
        <CardDescription>
          The total planned or known investment in the idea. Value for Money divides it by
          the IQ, so it is never shown to the AI.
        </CardDescription>
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <CurrencySelect value={values.currency} onChange={(code) => set("currency", code)} />
          <TextField
            label="Planned investment"
            name="investment"
            inputMode="decimal"
            placeholder="50000"
            error={errors.investment}
            value={values.investment}
            onChange={(e) => set("investment", e.target.value)}
          />
          <TextField
            label="Expected value"
            name="expected_value"
            inputMode="decimal"
            hint="Optional. What the idea is expected to bring in, in the same currency."
            error={errors.expected_value}
            value={values.expected_value}
            onChange={(e) => set("expected_value", e.target.value)}
          />
        </div>
      </Card>

      <div className="flex flex-wrap items-center gap-2">
        <Button type="submit" busy={busy}>
          {idea ? "Save changes" : "Save idea"}
        </Button>
        <Link
          href={idea ? `/ideas/${idea.id}` : "/ideas"}
          className="text-sm font-medium text-neutral-600 hover:text-neutral-900 hover:underline"
        >
          Cancel
        </Link>
      </div>
    </form>
  );
}
