/** A thin progress bar. Decorative: the figure next to it carries the meaning. */
export function Bar({
  value,
  maximum,
  tone = "primary",
}: {
  value: number;
  maximum: number;
  tone?: "primary" | "accent";
}) {
  return (
    <div className="mt-2 h-1.5 overflow-hidden rounded-sm bg-neutral-100" aria-hidden="true">
      <div
        className={`h-full rounded-sm transition-[width] ${tone === "accent" ? "bg-accent" : "bg-primary"}`}
        style={{ width: `${Math.round((value / maximum) * 100)}%` }}
      />
    </div>
  );
}
