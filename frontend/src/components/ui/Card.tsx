import type { ReactNode } from "react";

/** A bordered white panel. Sections of a page, never nested. */
export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <section
      className={`rounded-lg border border-neutral-200 bg-white p-5${className ? ` ${className}` : ""}`}
    >
      {children}
    </section>
  );
}

export function CardTitle({ children }: { children: ReactNode }) {
  return <h2 className="text-sm font-semibold text-neutral-900">{children}</h2>;
}

export function CardDescription({ children }: { children: ReactNode }) {
  return <p className="mt-1 text-sm text-neutral-600">{children}</p>;
}

/** A card's first row: title and description on the left, controls on the right. */
export function CardHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-2">
      <div className="min-w-0">
        <CardTitle>{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
      <div className="min-w-0">
        <h1 className="text-xl font-semibold text-neutral-900">{title}</h1>
        {description && <p className="mt-1 text-sm text-neutral-600">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

/** A small uppercase label above a figure or a group. */
export function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <p className="text-[11px] font-medium tracking-[0.06em] text-neutral-500 uppercase">
      {children}
    </p>
  );
}
