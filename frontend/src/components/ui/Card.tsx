import type { ReactNode } from "react";

export function Card({ children }: { children: ReactNode }) {
  return (
    <section className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm">
      {children}
    </section>
  );
}

export function CardTitle({ children }: { children: ReactNode }) {
  return <h2 className="text-base font-semibold text-neutral-900">{children}</h2>;
}

export function PageHeader({ title, description }: { title: string; description?: string }) {
  return (
    <header>
      <h1 className="text-2xl font-semibold tracking-tight text-neutral-900">{title}</h1>
      {description && <p className="mt-1 text-sm text-neutral-600">{description}</p>}
    </header>
  );
}
