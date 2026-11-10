import type { Direction } from "@/lib/api/types";

const MARKS: Record<Direction, string> = { up: "▲", down: "▼", same: "–" };
const WORDS: Record<Direction, string> = { up: "up", down: "down", same: "no change" };

/** How a figure moved since the result before it, as the server worked it out: an arrow
 * and the signed amount. It says which way the number went, not whether that is good
 * (a lower cost per innovation point is better). Null means there is nothing to compare. */
export function Change({
  change,
  direction,
}: {
  change: number | string | null;
  direction: Direction | null;
}) {
  if (change === null || direction === null) {
    return <span className="text-neutral-400">–</span>;
  }
  const amount = String(change).replace(/^-/, "");
  const signed = direction === "up" ? `+${amount}` : direction === "down" ? `−${amount}` : "0";
  return (
    <span className="whitespace-nowrap text-neutral-600 tabular-nums">
      <span aria-hidden="true" className="mr-1 text-[10px]">
        {MARKS[direction]}
      </span>
      {direction === "same" ? "no change" : signed}
      <span className="sr-only"> ({WORDS[direction]})</span>
    </span>
  );
}

/** The same in words, for a CSV cell: "up 5", "down 7", "no change". */
export function changeText(change: number | string | null, direction: Direction | null): string {
  if (change === null || direction === null) return "";
  if (direction === "same") return "no change";
  return `${direction} ${String(change).replace(/^-/, "")}`;
}
