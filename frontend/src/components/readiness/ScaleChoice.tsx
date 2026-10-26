import type { ReactNode } from "react";

/** The 1 to 5 answer control: one connected row of equal cells, the chosen one filled.
 * Each cell is a real radio, so keyboard and screen-reader behaviour come for free. */
export function ScaleChoice({
  name,
  scale,
  value,
  onChange,
  ariaLabel,
}: {
  name: string;
  scale: number[];
  value: number | null | undefined;
  onChange: (value: number) => void;
  /** The accessible name of each cell, from its value and the scale's label if any. */
  ariaLabel: (value: number) => string;
}) {
  return (
    <span className="inline-flex overflow-hidden rounded-md border border-neutral-300 bg-white shadow-xs has-[:disabled]:opacity-60 has-[:disabled]:shadow-none">
      {scale.map((option) => {
        const chosen = value === option;
        return (
          <label
            key={option}
            className={`relative flex h-9 w-10 cursor-pointer items-center justify-center border-l border-neutral-300 text-sm font-medium tabular-nums transition-colors first:border-l-0 has-[:focus-visible]:z-10 has-[:focus-visible]:outline-2 has-[:focus-visible]:-outline-offset-2 has-[:focus-visible]:outline-primary has-[:disabled]:cursor-not-allowed ${
              chosen ? "bg-primary text-white" : "text-neutral-700 hover:bg-neutral-50"
            }`}
          >
            <input
              type="radio"
              name={name}
              value={option}
              checked={chosen}
              onChange={() => onChange(option)}
              aria-label={ariaLabel(option)}
              className="sr-only"
            />
            {option}
          </label>
        );
      })}
    </span>
  );
}

/** A thin progress bar. Decorative: the figure next to it carries the meaning. */
export function Bar({ value, maximum, tone = "primary" }: { value: number; maximum: number; tone?: "primary" | "accent" }) {
  return (
    <div className="mt-2 h-1.5 overflow-hidden rounded-sm bg-neutral-100" aria-hidden="true">
      <div
        className={`h-full rounded-sm transition-[width] ${tone === "accent" ? "bg-accent" : "bg-primary"}`}
        style={{ width: `${Math.round((value / maximum) * 100)}%` }}
      />
    </div>
  );
}

/** A sticky toolbar under the header for progress, save state and the main action. */
export function StickyBar({ children }: { children: ReactNode }) {
  return (
    <div className="sticky top-(--app-header-h) z-10 -mx-4 border-y border-neutral-200 bg-white px-4 py-3 sm:mx-0 sm:rounded-lg sm:border">
      {children}
    </div>
  );
}
