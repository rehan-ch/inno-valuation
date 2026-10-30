import type { ReactNode } from "react";

/** A plain blank slate: what is missing and, when given, what to do about it. */
export function EmptyState({
  title,
  children,
  action,
}: {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-md border border-dashed border-neutral-300 px-6 py-10 text-center">
      <p className="text-sm font-medium text-neutral-900">{title}</p>
      {children && <p className="mx-auto mt-1 max-w-md text-sm text-neutral-600">{children}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
