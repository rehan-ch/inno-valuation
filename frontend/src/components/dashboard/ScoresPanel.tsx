"use client";

import Link from "next/link";
import { useId, useState } from "react";
import type { ReactNode } from "react";

import { Compass } from "@/components/compass/Compass";
import { buttonClass } from "@/components/ui/Button";
import { Card, CardDescription, CardHeader, Eyebrow } from "@/components/ui/Card";
import { dimensionHref } from "@/lib/api/insights";
import type { DashboardOut, IqHeadlineOut, ReadinessHeadlineOut } from "@/lib/api/types";
import { formatDate } from "@/lib/format";
import { formatMoney } from "@/lib/money";

import { PriorityList } from "./PriorityList";

type View = "readiness" | "iq";

/** The two headline scores side by side: the organisation's readiness out of 300 with its
 * band, and the selected idea's IQ out of 100. They are two separate measures and are
 * never added, averaged or shown as one number. Below them, the compass and the priorities
 * of whichever one is chosen. `fallback` fills a side that has no result yet. */
export function ScoresPanel({
  dashboard,
  onSelectIdea,
  selecting = false,
  readinessFallback,
  iqFallback,
}: {
  dashboard: DashboardOut;
  onSelectIdea: (ideaId: string) => void;
  selecting?: boolean;
  readinessFallback: ReactNode;
  iqFallback: ReactNode;
}) {
  const { readiness, iq } = dashboard;
  const [chosen, setChosen] = useState<View>("readiness");
  const view: View | null =
    readiness && iq ? chosen : readiness ? "readiness" : iq ? "iq" : null;

  return (
    <>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {readiness ? <ReadinessHeadline readiness={readiness} /> : readinessFallback}
        {iq ? (
          <IqHeadline
            iq={iq}
            ideas={dashboard.ideas}
            onSelectIdea={onSelectIdea}
            selecting={selecting}
          />
        ) : (
          iqFallback
        )}
      </div>

      {view && (
        <Card>
          <CardHeader
            title={view === "readiness" ? "Readiness compass" : "Idea compass"}
            description={
              view === "readiness"
                ? "How ready the organisation is on each of the 12 dimensions, from the agreed answers."
                : `The confirmed scores of "${iq?.idea_title}" on each of the 12 dimensions.`
            }
            actions={
              readiness && iq ? (
                <div
                  role="group"
                  aria-label="Which compass to show"
                  className="inline-flex rounded-md border border-neutral-300 bg-white p-0.5 shadow-xs"
                >
                  {(["readiness", "iq"] as const).map((option) => (
                    <button
                      key={option}
                      type="button"
                      aria-pressed={view === option}
                      onClick={() => setChosen(option)}
                      className={`h-7 rounded-[5px] px-2.5 text-[13px] font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${
                        view === option
                          ? "bg-neutral-900 text-white"
                          : "text-neutral-700 hover:bg-neutral-100"
                      }`}
                    >
                      {option === "readiness" ? "Readiness" : "Idea IQ"}
                    </button>
                  ))}
                </div>
              ) : null
            }
          />
          <div className="mt-5">
            {view === "readiness" && readiness && (
              <Compass
                title="Readiness compass"
                compass={readiness.compass}
                headline={{
                  value: String(readiness.total),
                  maximum: String(readiness.total_maximum),
                  label: readiness.band.name,
                }}
                hrefFor={(key) => dimensionHref(key, iq?.idea_id)}
              />
            )}
            {view === "iq" && iq && (
              <Compass
                title="Idea compass"
                compass={iq.compass}
                headline={{ value: iq.iq, maximum: trimZero(iq.iq_maximum), label: "Innovation Quotient" }}
                hrefFor={(key) => dimensionHref(key, iq.idea_id)}
              />
            )}
          </div>
        </Card>
      )}

      {view && (
        <Card>
          <CardHeader
            title={view === "readiness" ? "Readiness priorities" : "Idea priorities"}
            description={
              <>
                The lowest-scoring dimensions, with the next steps from the method.
                {view === "iq" && iq?.custom_weights && (
                  <>
                    {" "}
                    Where scores tie, the more important dimension comes first, as set in your{" "}
                    <Link
                      href="/organisation/importance"
                      className="font-medium text-primary hover:underline"
                    >
                      dimension importance
                    </Link>
                    . Importance never changes a score.
                  </>
                )}
              </>
            }
          />
          <div className="mt-4">
            {view === "readiness" && readiness && (
              <PriorityList
                priorities={readiness.priorities}
                hrefFor={(key) => dimensionHref(key, iq?.idea_id)}
              />
            )}
            {view === "iq" && iq && (
              <PriorityList
                priorities={iq.priorities}
                hrefFor={(key) => dimensionHref(key, iq.idea_id)}
              />
            )}
          </div>
        </Card>
      )}
    </>
  );
}

/** "100.0" reads as "100" beside "out of"; the figure itself is the server's. */
function trimZero(value: string): string {
  return value.replace(/\.0+$/, "");
}

function ReadinessHeadline({ readiness }: { readiness: ReadinessHeadlineOut }) {
  return (
    <Card>
      <CardHeader title="Innovation Readiness" description="The whole organisation." />
      <div className="mt-4">
        <Eyebrow>Readiness score</Eyebrow>
        <p className="mt-1.5 text-4xl font-semibold tracking-tight text-neutral-900 tabular-nums">
          {readiness.total}
          <span className="ml-1.5 text-lg font-normal text-neutral-500">
            / {readiness.total_maximum}
          </span>
        </p>
        <p className="mt-3 text-sm font-semibold text-neutral-900">{readiness.band.name}</p>
        <CardDescription>{readiness.band.text}</CardDescription>
        <p className="mt-2 text-xs text-neutral-500">Final on {formatDate(readiness.finalised_at)}.</p>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <Link
          href={`/readiness/${readiness.assessment_id}/result`}
          className={buttonClass("secondary", "sm")}
        >
          See the result
        </Link>
        <Link href="/history" className={buttonClass("ghost", "sm")}>
          History
        </Link>
      </div>
    </Card>
  );
}

function IqHeadline({
  iq,
  ideas,
  onSelectIdea,
  selecting,
}: {
  iq: IqHeadlineOut;
  ideas: DashboardOut["ideas"];
  onSelectIdea: (ideaId: string) => void;
  selecting: boolean;
}) {
  const selectId = useId();
  return (
    <Card>
      <CardHeader
        title="Innovation Quotient"
        description="One idea at a time."
        actions={
          ideas.length > 1 ? (
            <>
              <label htmlFor={selectId} className="sr-only">
                Idea
              </label>
              <select
                id={selectId}
                value={iq.idea_id}
                disabled={selecting}
                onChange={(event) => onSelectIdea(event.target.value)}
                className="h-8 max-w-56 rounded-md border border-neutral-300 bg-white px-2 text-[13px] text-neutral-900 shadow-xs focus:outline-2 focus:-outline-offset-1 focus:outline-primary"
              >
                {ideas.map((idea) => (
                  <option key={idea.idea_id} value={idea.idea_id}>
                    {idea.title}
                  </option>
                ))}
              </select>
            </>
          ) : null
        }
      />
      <div className="mt-4" aria-busy={selecting || undefined}>
        <Eyebrow>IQ of {iq.idea_title}</Eyebrow>
        <p className="mt-1.5 text-4xl font-semibold tracking-tight text-neutral-900 tabular-nums">
          {iq.iq}
          <span className="ml-1.5 text-lg font-normal text-neutral-500">
            / {trimZero(iq.iq_maximum)}
          </span>
        </p>
        <p className="mt-3 text-sm font-semibold text-neutral-900">Value for money</p>
        <CardDescription>
          {iq.vfm?.per_point
            ? `${formatMoney(iq.vfm.per_point, iq.vfm.currency)} per innovation point. Lower is better.`
            : `Not calculable. ${iq.vfm?.not_calculable_reason ?? ""}`.trim()}
        </CardDescription>
        <p className="mt-2 text-xs text-neutral-500">Confirmed on {formatDate(iq.confirmed_at)}.</p>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <Link
          href={`/ideas/${iq.idea_id}/assessments/${iq.assessment_id}`}
          className={buttonClass("secondary", "sm")}
        >
          See the result
        </Link>
        <Link href={`/history?idea=${iq.idea_id}`} className={buttonClass("ghost", "sm")}>
          History
        </Link>
      </div>
    </Card>
  );
}
