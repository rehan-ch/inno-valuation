import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main id="main" className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-4 py-10">
      <p className="mb-6 flex items-center justify-center">
        <Link href="/" className="flex items-center gap-2">
          <Image src="/innovaluation-mark.png" alt="" width={32} height={31} />
          <span className="bg-linear-to-r from-primary to-accent bg-clip-text font-serif text-xl font-semibold tracking-tight text-transparent">
            InnoValuation
          </span>
        </Link>
      </p>
      <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm">{children}</div>
    </main>
  );
}
