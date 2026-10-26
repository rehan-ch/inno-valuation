export function Loading({ children = "Loading..." }: { children?: string }) {
  return (
    <p role="status" aria-live="polite" className="flex items-center gap-2 text-sm text-neutral-600">
      <span
        aria-hidden="true"
        className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-neutral-300 border-t-neutral-700 motion-reduce:animate-none"
      />
      {children}
    </p>
  );
}
