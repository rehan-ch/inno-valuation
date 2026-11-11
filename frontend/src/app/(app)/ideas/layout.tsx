"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { useMe } from "@/components/app/me-context";
import { buttonClass } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";

/** Ideas are scored by the AI, so without it the pages are closed rather than shown with
 * a proposal that can never arrive. */
export default function IdeasLayout({ children }: { children: ReactNode }) {
  const { me } = useMe();
  if (me.ai_enabled) return children;
  return (
    <div className="space-y-6">
      <PageHeader title="Ideas" />
      <EmptyState
        title="Idea scoring is not available yet"
        action={
          <Link href="/dashboard" className={buttonClass("secondary", "sm")}>
            Back to the dashboard
          </Link>
        }
      >
        Scoring an idea is switched off for now. The readiness assessment, targets and history
        work as usual.
      </EmptyState>
    </div>
  );
}
