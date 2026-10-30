import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main id="main" className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center px-4 py-10">
      <p className="mb-6 flex items-center justify-center">
        <Link href="/" className="flex items-center gap-2 rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary">
          <Image src="/innovaluation-mark.png" alt="" width={28} height={27} />
          <span className="text-base font-semibold tracking-tight text-neutral-900">InnoValuation</span>
        </Link>
      </p>
      <div className="rounded-lg border border-neutral-200 bg-white p-6">{children}</div>
    </main>
  );
}
