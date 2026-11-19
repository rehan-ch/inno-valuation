import type { ReactNode } from "react";

import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Loading } from "@/components/ui/Loading";
import type {
  AdviceOut,
  AdvicePartName,
  AdvicePartStatus,
  AdviceUsageOut,
  RecommendationOut,
} from "@/lib/api/types";
import { formatDate } from "@/lib/format";

/** The common facts of one part of the advice. */
export interface PartMeta {
  status: AdvicePartStatus;
  sample: boolean;
  outdated: boolean;
  generated_at: string | null;
  usage: AdviceUsageOut | null;
}

export type Ask = (options: { parts?: AdvicePartName[]; regenerate?: boolean }) => void;

/** Marks text as the AI's, so it is never read as the method's own words. */
export function ProposedByAi({ sample }: { sample: boolean }) {
  return sample ? (
    <Badge tone="amber">Sample text</Badge>
  ) : (
    <Badge tone="blue" dot={false}>
      Proposed by AI
    </Badge>
  );
}

function Usage({ usage }: { usage: AdviceUsageOut }) {
  // Shown to platform admins only (the API sends it to nobody else). The cost comes as
  // text, already in dollars: nothing is calculated here.
  return (
    <p className="mt-2 text-xs text-neutral-500">
      Usage (platform admins only): {usage.model ?? "unknown model"} ·{" "}
      {usage.input_tokens.toLocaleString()} tokens in · {usage.output_tokens.toLocaleString()} out ·
      US${usage.cost_usd}
    </p>
  );
}

/** True in every case the server calls advice out of date: a target, the company details,
 * the prompt or the AI model changed after it was written. */
export const OUTDATED_TEXT = "This was written before something it is based on changed.";

/** Shown instead of a spinner once the page has stopped checking for pending advice. */
export function StillWorking({ onCheckAgain }: { onCheckAgain: () => void }) {
  return (
    <Alert tone="info">
      <p>This is taking longer than usual. The AI may still be working on it.</p>
      <Button variant="secondary" size="sm" className="mt-2" onClick={onCheckAgain}>
        Check again
      </Button>
    </Alert>
  );
}

/** One part of the advice: its heading, its state in words, the way to ask or ask again,
 * and the content when there is some. `mixed` says the content also holds the method's
 * own text: then the content marks which blocks are the AI's, and the heading does not. */
export function PartSection({
  title,
  part,
  meta,
  hasContent,
  canRequest,
  busy,
  onAsk,
  pendingText,
  stalled = false,
  mixed = false,
  children,
}: {
  title: string;
  part: AdvicePartName;
  meta: PartMeta;
  hasContent: boolean;
  canRequest: boolean;
  busy: boolean;
  onAsk: Ask;
  pendingText: string;
  stalled?: boolean;
  mixed?: boolean;
  children: ReactNode;
}) {
  if (meta.status === "off") return null;
  const pending = meta.status === "pending";
  const askLabel = hasContent ? "Ask again" : meta.status === "failed" ? "Try again" : "Ask the AI";
  return (
    <section aria-label={title} className="border-t border-neutral-200 pt-5 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-semibold text-neutral-900">{title}</h3>
          {hasContent && !mixed && <ProposedByAi sample={meta.sample} />}
        </div>
        {canRequest && !pending && (
          <Button
            variant="secondary"
            size="sm"
            busy={busy}
            // Four parts share the visible words; the name says which part this one asks for.
            aria-label={`${askLabel}: ${title}`}
            onClick={() => onAsk({ parts: [part], regenerate: hasContent })}
          >
            {askLabel}
          </Button>
        )}
      </div>
      <div className="mt-3 space-y-3">
        {pending && !stalled && <Loading>{pendingText}</Loading>}
        {pending && stalled && <p className="text-sm text-neutral-600">Not ready yet.</p>}
        {meta.status === "failed" && (
          <Alert tone="error">
            {hasContent
              ? "The last attempt to refresh this did not work. The earlier text is still shown."
              : "The AI could not write this right now."}
          </Alert>
        )}
        {meta.status === "none" && !canRequest && (
          <p className="text-sm text-neutral-600">Nobody has asked for this yet.</p>
        )}
        {hasContent && meta.outdated && !pending && (
          <Alert tone="info">
            {OUTDATED_TEXT}
            {canRequest ? " Ask again to bring it up to date." : ""}
          </Alert>
        )}
        {hasContent && children}
        {hasContent && meta.generated_at && (
          <p className="text-xs text-neutral-500">
            {meta.sample
              ? "Sample text: the AI is not connected yet."
              : mixed
                ? `The text marked "Proposed by AI" was written by AI on ${formatDate(meta.generated_at)}. It can be wrong, so use your own judgement. The method's next steps are shown as written.`
                : `Written by AI on ${formatDate(meta.generated_at)}. It can be wrong, so use your own judgement.`}
          </p>
        )}
        {meta.usage && <Usage usage={meta.usage} />}
      </div>
    </section>
  );
}

export function Sentences({ items }: { items: string[] }) {
  return (
    <ul className="list-disc space-y-1 pl-4 text-sm text-neutral-700">
      {items.map((sentence, i) => (
        // Keyed by position: the list is fixed and two sentences may be equal.
        <li key={i}>{sentence}</li>
      ))}
    </ul>
  );
}

function Group({ label, items }: { label: string; items: string[] }) {
  return (
    <div>
      <p className="text-xs font-medium text-neutral-500">{label}</p>
      <div className="mt-1">
        <Sentences items={items} />
      </div>
    </div>
  );
}

/** One recommendation: the method's fixed next steps, set apart, then the AI's advice,
 * which alone carries the AI mark. */
export function RecommendationBody({ item, sample }: { item: RecommendationOut; sample: boolean }) {
  return (
    <div className="space-y-3">
      <div>
        <p className="text-xs font-medium text-neutral-500">Next steps from the method, as written</p>
        <p className="mt-1 border-l-2 border-primary pl-3 text-sm text-neutral-800">
          {item.fixed_text}
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-xs font-medium text-neutral-500">The AI&apos;s advice</p>
        <ProposedByAi sample={sample} />
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Group label="Initiatives" items={item.initiatives} />
        <Group label="What to measure" items={item.kpis} />
        <Group label="Timeline" items={[item.timeline]} />
        <Group label="What it needs" items={item.resources} />
      </div>
    </div>
  );
}

/** The consultation suggestion, when the AI made one. */
export function ConsultationMessage({ consultation }: { consultation: AdviceOut["consultation"] }) {
  return (
    <div className="rounded-md border border-primary/20 bg-primary-soft px-3.5 py-3 text-sm">
      <p className="font-medium text-neutral-900">{consultation.message.join(" ")}</p>
      <ul className="mt-2 space-y-1 text-neutral-700">
        {consultation.reasons.map((reason) => (
          <li key={reason.key}>
            <span className="font-medium text-neutral-900">{reason.name}: </span>
            {reason.reason}
          </li>
        ))}
      </ul>
    </div>
  );
}
