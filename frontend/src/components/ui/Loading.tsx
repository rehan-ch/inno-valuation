export function Loading({ children = "Loading..." }: { children?: string }) {
  return (
    <p role="status" aria-live="polite" className="text-sm text-neutral-600">
      {children}
    </p>
  );
}
