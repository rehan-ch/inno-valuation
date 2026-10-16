import Link from "next/link";
import type { ReactNode } from "react";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main id="main" className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-4 py-10">
      <p className="mb-6 text-center">
        <Link href="/" className="text-lg font-semibold text-neutral-900">
          InnoValuation
        </Link>
      </p>
      <div className="rounded-lg border border-neutral-200 bg-white p-6 shadow-sm">{children}</div>
    </main>
  );
}
