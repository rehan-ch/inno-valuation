import Link from "next/link";

import type { PriorityItemOut } from "@/lib/api/types";

/** The lowest-scoring dimensions as the scoring engine ranked them, each with the book's
 * next steps as written. Nothing is sorted or filtered here. */
export function PriorityList({
  priorities,
  hrefFor,
}: {
  priorities: PriorityItemOut[];
  hrefFor: (key: string) => string;
}) {
  return (
    <ol className="divide-y divide-neutral-100">
      {priorities.map((priority) => (
        <li key={priority.key} className="flex gap-3 py-3 first:pt-0 last:pb-0">
          <span className="w-5 shrink-0 text-sm font-semibold text-neutral-400 tabular-nums">
            {priority.rank}
          </span>
          <span className="min-w-0 flex-1">
            <span className="flex items-baseline justify-between gap-3 text-sm">
              <Link
                href={hrefFor(priority.key)}
                className="font-medium text-neutral-900 hover:text-primary hover:underline"
              >
                {priority.name}
              </Link>
              <span className="shrink-0 text-neutral-500 tabular-nums">
                {priority.score} / {priority.maximum}
                {priority.level_name ? ` · ${priority.level_name}` : ""}
              </span>
            </span>
            <span className="mt-0.5 block text-sm text-neutral-600">{priority.next_steps}</span>
          </span>
        </li>
      ))}
    </ol>
  );
}
