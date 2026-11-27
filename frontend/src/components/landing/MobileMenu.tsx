"use client";

import { useRef } from "react";
import type { ReactNode } from "react";

/** The landing page's phone menu: a <details> that closes once one of its links is used,
    so the in-page links do not leave it open over the section they scroll to. */
export function MobileMenu({ className, children }: { className?: string; children: ReactNode }) {
  const menu = useRef<HTMLDetailsElement>(null);
  return (
    <details
      ref={menu}
      className={className}
      onClick={(event) => {
        if ((event.target as HTMLElement).closest("a")) menu.current?.removeAttribute("open");
      }}
    >
      {children}
    </details>
  );
}
