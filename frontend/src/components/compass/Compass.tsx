"use client";

import Link from "next/link";
import { useId, useState } from "react";

import type { CompassOut, CompassSegmentOut } from "@/lib/api/types";

// Geometry of the drawing, in viewBox units. Nothing here is a score: a segment's bar
// reaches the share of the ring that its score is of its maximum, both sent by the server.
const SIZE = 420;
const CENTRE = SIZE / 2;
const INNER = 64;
const OUTER = 138;
const NUMBER_RADIUS = 150;
const CATEGORY_RADIUS = 163;
const CATEGORY_TEXT_RADIUS = 170;
const START_ANGLE = -90; // the first dimension starts at the top
// Ordered levels take the one-hue ramp, lightest first (globals.css).
const RAMP = ["var(--color-ramp-1)", "var(--color-ramp-2)", "var(--color-ramp-3)"];
const SINGLE = "var(--color-primary)";

function point(radius: number, degrees: number): [number, number] {
  const radians = (degrees * Math.PI) / 180;
  return [CENTRE + radius * Math.cos(radians), CENTRE + radius * Math.sin(radians)];
}

function fixed(value: number): string {
  return value.toFixed(2);
}

/** A ring slice between two radii and two angles (degrees, clockwise from the right). */
function slice(inner: number, outer: number, from: number, to: number): string {
  const [x1, y1] = point(outer, from);
  const [x2, y2] = point(outer, to);
  const [x3, y3] = point(inner, to);
  const [x4, y4] = point(inner, from);
  const large = to - from > 180 ? 1 : 0;
  return [
    `M ${fixed(x1)} ${fixed(y1)}`,
    `A ${outer} ${outer} 0 ${large} 1 ${fixed(x2)} ${fixed(y2)}`,
    `L ${fixed(x3)} ${fixed(y3)}`,
    `A ${inner} ${inner} 0 ${large} 0 ${fixed(x4)} ${fixed(y4)}`,
    "Z",
  ].join(" ");
}

function arc(radius: number, from: number, to: number, clockwise = true): string {
  const [x1, y1] = point(radius, clockwise ? from : to);
  const [x2, y2] = point(radius, clockwise ? to : from);
  const large = Math.abs(to - from) > 180 ? 1 : 0;
  return `M ${fixed(x1)} ${fixed(y1)} A ${radius} ${radius} 0 ${large} ${clockwise ? 1 : 0} ${fixed(x2)} ${fixed(y2)}`;
}

function radiusAt(value: number, maximum: number): number {
  const share = Math.max(0, Math.min(1, value / maximum));
  return INNER + (OUTER - INNER) * share;
}

/** The colour of a segment: its level's place on the ramp, or the one colour when the
 * scale has no levels. Chosen by position, so no level is known by name here. */
function fillOf(segment: CompassSegmentOut, levelCount: number): string {
  if (!segment.level || levelCount === 0) return SINGLE;
  const place = levelCount === 1 ? 1 : (segment.level.order - 1) / (levelCount - 1);
  return RAMP[Math.round(place * (RAMP.length - 1))] ?? SINGLE;
}

function gapWords(gap: number): string {
  if (gap > 0) return `${gap} below target`;
  if (gap < 0) return `${-gap} above target`;
  return "on target";
}

function describe(segment: CompassSegmentOut): string {
  const parts = [`${segment.name}: ${segment.score} out of ${segment.maximum}`];
  if (segment.level) parts.push(segment.level.name);
  if (segment.target !== null && segment.gap !== null) {
    parts.push(`target ${segment.target}, ${gapWords(segment.gap)}`);
  }
  return parts.join(", ");
}

export interface CompassProps {
  compass: CompassOut;
  /** What the middle of the compass shows: the result's headline figure. */
  headline: { value: string; maximum: string; label: string };
  /** Where a dimension's segment and table row lead. */
  hrefFor: (key: string) => string;
  /** Names the chart for screen readers, e.g. "Readiness compass". */
  title: string;
}

/** The 12 Dimensions of Innovation compass for one result: 12 segments in book order,
 * grouped into the 3 categories, with a legend and a table of the same numbers. It draws
 * what the server sent: the order, the categories, each score and maximum, the level and
 * the target all come from the payload. */
export function Compass({ compass, headline, hrefFor, title }: CompassProps) {
  const id = useId();
  const [active, setActive] = useState<string | null>(null);
  const count = compass.segments.length;
  const step = 360 / count;
  const levelCount = compass.levels.length;
  const shown = compass.segments.find((s) => s.key === active) ?? null;
  const hasTargets = compass.segments.some((s) => s.target !== null);
  const index = new Map(compass.segments.map((s, i) => [s.key, i]));

  return (
    <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,25rem)_1fr]">
      <div>
        <svg
          viewBox={`0 0 ${SIZE} ${SIZE}`}
          role="group"
          aria-label={`${title}: ${count} dimensions in ${compass.categories.length} categories`}
          className="mx-auto block w-full max-w-100"
          onMouseLeave={() => setActive(null)}
        >
          {compass.categories.map((category) => {
            const places = category.dimension_keys
              .map((key) => index.get(key))
              .filter((i): i is number => i !== undefined);
            if (places.length === 0) return null;
            const from = START_ANGLE + Math.min(...places) * step + 1.5;
            const to = START_ANGLE + (Math.max(...places) + 1) * step - 1.5;
            const middle = (((from + to) / 2) % 360 + 360) % 360;
            // In the lower half the label runs the other way, so it is never upside down.
            const lower = middle > 0 && middle < 180;
            const pathId = `${id}-${category.key}`;
            return (
              <g key={category.key}>
                <path
                  d={arc(CATEGORY_RADIUS, from, to)}
                  fill="none"
                  stroke="var(--color-neutral-300)"
                  strokeWidth={2}
                  strokeLinecap="round"
                />
                <path
                  id={pathId}
                  d={arc(lower ? CATEGORY_TEXT_RADIUS + 9 : CATEGORY_TEXT_RADIUS, from, to, !lower)}
                  fill="none"
                />
                <text
                  fontSize={10.5}
                  fontWeight={500}
                  letterSpacing={0.6}
                  fill="var(--color-neutral-600)"
                  aria-hidden="true"
                >
                  <textPath href={`#${pathId}`} startOffset="50%" textAnchor="middle">
                    {category.name.toUpperCase()}
                  </textPath>
                </text>
              </g>
            );
          })}

          {compass.segments.map((segment, i) => {
            const from = START_ANGLE + i * step;
            const to = from + step;
            const [nx, ny] = point(NUMBER_RADIUS, from + step / 2);
            const isActive = active === segment.key;
            return (
              <Link
                key={segment.key}
                href={hrefFor(segment.key)}
                aria-label={describe(segment)}
                className="outline-none [&:focus-visible>.focus-mark]:opacity-100"
                onMouseEnter={() => setActive(segment.key)}
                onFocus={() => setActive(segment.key)}
                onBlur={() => setActive(null)}
              >
                <title>{describe(segment)}</title>
                <path
                  d={slice(INNER, OUTER, from, to)}
                  fill={isActive ? "var(--color-neutral-200)" : "var(--color-neutral-100)"}
                  stroke="white"
                  strokeWidth={2}
                />
                <path
                  d={slice(INNER, radiusAt(segment.score, segment.maximum), from, to)}
                  fill={fillOf(segment, levelCount)}
                  stroke="white"
                  strokeWidth={2}
                />
                {segment.target !== null && (
                  <path
                    d={arc(radiusAt(segment.target, segment.maximum), from + 2.5, to - 2.5)}
                    fill="none"
                    stroke="var(--color-neutral-900)"
                    strokeWidth={2}
                    strokeDasharray="3 3"
                  />
                )}
                <path
                  className="focus-mark opacity-0"
                  d={slice(INNER - 3, OUTER + 3, from + 0.5, to - 0.5)}
                  fill="none"
                  stroke="var(--color-neutral-900)"
                  strokeWidth={2}
                />
                <text
                  x={fixed(nx)}
                  y={fixed(ny)}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontSize={11}
                  fontWeight={isActive ? 700 : 500}
                  fill={isActive ? "var(--color-neutral-900)" : "var(--color-neutral-500)"}
                  aria-hidden="true"
                >
                  {segment.order}
                </text>
              </Link>
            );
          })}

          <g aria-hidden="true" textAnchor="middle">
            {shown ? (
              <>
                <text x={CENTRE} y={CENTRE - 6} fontSize={26} fontWeight={600} fill="var(--color-neutral-900)">
                  {shown.score}
                  <tspan fontSize={13} fontWeight={400} fill="var(--color-neutral-500)">
                    {" "}
                    / {shown.maximum}
                  </tspan>
                </text>
                <text x={CENTRE} y={CENTRE + 14} fontSize={10.5} fill="var(--color-neutral-600)">
                  {shown.order}. {shown.name}
                </text>
                {shown.level && (
                  <text x={CENTRE} y={CENTRE + 29} fontSize={10.5} fill="var(--color-neutral-500)">
                    {shown.level.name}
                  </text>
                )}
              </>
            ) : (
              <>
                <text x={CENTRE} y={CENTRE - 2} fontSize={30} fontWeight={600} fill="var(--color-neutral-900)">
                  {headline.value}
                </text>
                <text x={CENTRE} y={CENTRE + 17} fontSize={11.5} fill="var(--color-neutral-500)">
                  out of {headline.maximum}
                </text>
                <text x={CENTRE} y={CENTRE + 33} fontSize={10.5} fill="var(--color-neutral-500)">
                  {headline.label}
                </text>
              </>
            )}
          </g>
        </svg>

        <div className="mt-3 space-y-1.5 text-xs text-neutral-600">
          {levelCount > 0 ? (
            <ul aria-label="Levels" className="flex flex-wrap justify-center gap-x-4 gap-y-1">
              {compass.levels.map((level) => (
                <li key={level.key} className="flex items-center gap-1.5">
                  <span
                    aria-hidden="true"
                    className="h-2.5 w-2.5 rounded-xs"
                    style={{
                      background: fillOf(
                        { level: { key: level.key, name: level.name, order: level.order } } as CompassSegmentOut,
                        levelCount,
                      ),
                    }}
                  />
                  {level.name}{" "}
                  <span className="text-neutral-500 tabular-nums">
                    {level.min} to {level.max}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-center">
              Each segment fills as far as its score out of {compass.maximum}.
            </p>
          )}
          {hasTargets && (
            <p className="flex items-center justify-center gap-1.5">
              <span
                aria-hidden="true"
                className="inline-block w-4 border-t-2 border-dashed border-neutral-900"
              />
              Target
            </p>
          )}
        </div>
      </div>

      <div className="min-w-0">
        <div className="overflow-x-auto rounded-md border border-neutral-200">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">{title}: every dimension&apos;s score</caption>
            <thead className="bg-neutral-50">
              <tr className="border-b border-neutral-200 text-xs font-medium text-neutral-500">
                <th scope="col" className="px-3 py-2 font-medium">
                  Dimension
                </th>
                <th scope="col" className="px-3 py-2 text-right font-medium">
                  Score
                </th>
                {levelCount > 0 && (
                  <th scope="col" className="px-3 py-2 font-medium">
                    Level
                  </th>
                )}
                {hasTargets && (
                  <th scope="col" className="px-3 py-2 text-right font-medium">
                    Target
                  </th>
                )}
                {hasTargets && (
                  <th scope="col" className="px-3 py-2 font-medium">
                    Gap
                  </th>
                )}
              </tr>
            </thead>
            {compass.categories.map((category) => (
              <tbody key={category.key} className="divide-y divide-neutral-100 bg-white">
                <tr className="border-t border-neutral-200 bg-neutral-50/60">
                  <th
                    scope="rowgroup"
                    className="px-3 py-1.5 text-xs font-medium text-neutral-600"
                  >
                    {category.name}
                  </th>
                  <td className="px-3 py-1.5 text-right text-xs whitespace-nowrap text-neutral-600 tabular-nums">
                    {category.score} / {category.maximum}
                  </td>
                  {levelCount > 0 && <td />}
                  {hasTargets && <td />}
                  {hasTargets && <td />}
                </tr>
                {compass.segments
                  .filter((segment) => segment.category === category.key)
                  .map((segment) => (
                    <tr
                      key={segment.key}
                      className={active === segment.key ? "bg-primary-soft/60" : undefined}
                      onMouseEnter={() => setActive(segment.key)}
                      onMouseLeave={() => setActive(null)}
                    >
                      <th scope="row" className="px-3 py-1.5 font-normal">
                        <Link
                          href={hrefFor(segment.key)}
                          className="text-neutral-900 hover:text-primary hover:underline"
                        >
                          <span className="mr-2 inline-block w-4 text-neutral-400 tabular-nums">
                            {segment.order}
                          </span>
                          {segment.name}
                        </Link>
                        {segment.priority_rank !== null && (
                          <span className="ml-2 text-xs text-neutral-500">
                            priority {segment.priority_rank}
                          </span>
                        )}
                      </th>
                      <td className="px-3 py-1.5 text-right whitespace-nowrap tabular-nums">
                        <span className="font-medium text-neutral-900">{segment.score}</span>
                        <span className="text-neutral-500"> / {segment.maximum}</span>
                      </td>
                      {levelCount > 0 && (
                        <td className="px-3 py-1.5 whitespace-nowrap text-neutral-600">
                          {segment.level?.name ?? "–"}
                        </td>
                      )}
                      {hasTargets && (
                        <td className="px-3 py-1.5 text-right text-neutral-600 tabular-nums">
                          {segment.target ?? "–"}
                        </td>
                      )}
                      {hasTargets && (
                        <td className="px-3 py-1.5 whitespace-nowrap text-neutral-600">
                          {segment.gap !== null ? gapWords(segment.gap) : "–"}
                        </td>
                      )}
                    </tr>
                  ))}
              </tbody>
            ))}
          </table>
        </div>
      </div>
    </div>
  );
}

export { gapWords };
