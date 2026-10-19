import Image from "next/image";
import Link from "next/link";

export default function Home() {
  return (
    <main id="main" className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-4 py-10">
      <Image src="/innovaluation-mark.png" alt="" width={56} height={54} />
      <h1 className="mt-4 text-3xl font-semibold tracking-tight">
        <span className="bg-linear-to-r from-primary to-accent bg-clip-text text-transparent">
          InnoValuation
        </span>
      </h1>
      <p className="mt-2 text-neutral-600">Innovation diagnostic platform.</p>
      <div className="mt-6 flex gap-3">
        <Link
          href="/sign-in"
          className="inline-flex items-center justify-center rounded-full bg-primary px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-strong"
        >
          Sign in
        </Link>
        <Link
          href="/sign-up"
          className="inline-flex items-center justify-center rounded-full border border-neutral-300 bg-white px-5 py-2 text-sm font-medium text-neutral-900 transition-colors hover:bg-neutral-50"
        >
          Create an account
        </Link>
      </div>
      <p className="mt-6 text-sm">
        <Link href="/health" className="underline">
          Check system health
        </Link>
      </p>
    </main>
  );
}
