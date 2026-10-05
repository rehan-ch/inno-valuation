import type { Metadata } from "next";
import Link from "next/link";

import { HealthStatus } from "@/components/health/HealthStatus";

export const metadata: Metadata = {
  title: "System health | InnoValuation",
};

export default function HealthPage() {
  return (
    <main className="mx-auto w-full max-w-md flex-1 px-4 py-10">
      <h1 className="text-2xl font-semibold">System health</h1>
      <p className="mt-2 text-sm text-neutral-600">This page checks that the API and database are up.</p>
      <div className="mt-6">
        <HealthStatus />
      </div>
      <p className="mt-6 text-sm">
        <Link href="/" className="underline">
          Back to home
        </Link>
      </p>
    </main>
  );
}
