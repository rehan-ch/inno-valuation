"use client";

import { useEffect, useRef } from "react";
import type { ReactNode } from "react";

/** A sticky toolbar under the app header for progress, save state and the main action.
 * It publishes its height as --sticky-bar-h, so anchored sections can scroll clear of it
 * (see `stickyScrollMargin`) however many lines its content wraps to. */
export function StickyBar({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const root = document.documentElement;
    const publish = () => root.style.setProperty("--sticky-bar-h", `${element.offsetHeight}px`);
    publish();
    const observer = new ResizeObserver(publish);
    observer.observe(element);
    return () => {
      observer.disconnect();
      root.style.removeProperty("--sticky-bar-h");
    };
  }, []);

  return (
    <div
      ref={ref}
      className="sticky top-(--app-header-h) z-10 -mx-4 border-y border-neutral-200 bg-white px-4 py-3 sm:mx-0 sm:rounded-lg sm:border"
    >
      {children}
    </div>
  );
}

/** scroll-margin-top for a section linked from inside a StickyBar: the header, the bar
 * and a little air. */
export const stickyScrollMargin =
  "scroll-mt-[calc(var(--app-header-h)+var(--sticky-bar-h,0px)+1rem)]";
