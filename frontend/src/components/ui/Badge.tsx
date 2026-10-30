import type { ReactNode } from "react";

type Tone = "neutral" | "green" | "amber" | "red" | "blue";

const TONES: Record<Tone, string> = {
  neutral: "border-neutral-200 bg-neutral-50 text-neutral-700",
  green: "border-emerald-200 bg-emerald-50 text-emerald-800",
  amber: "border-amber-200 bg-amber-50 text-amber-800",
  red: "border-red-200 bg-red-50 text-red-800",
  blue: "border-primary/20 bg-primary-soft text-primary-strong",
};

const DOTS: Record<Tone, string> = {
  neutral: "bg-neutral-400",
  green: "bg-emerald-500",
  amber: "bg-amber-500",
  red: "bg-red-500",
  blue: "bg-primary",
};

/** A short status label. The dot carries the tone for anyone who does not read colour
 * as a hue; the words carry the meaning. */
export function Badge({
  tone = "neutral",
  dot = true,
  children,
}: {
  tone?: Tone;
  dot?: boolean;
  children: ReactNode;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border px-1.5 py-0.5 text-xs font-medium whitespace-nowrap ${TONES[tone]}`}
    >
      {dot && <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${DOTS[tone]}`} />}
      {children}
    </span>
  );
}
