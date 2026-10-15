import Link from "next/link";

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-4 py-10">
      <h1 className="text-3xl font-semibold">InnoValuation</h1>
      <p className="mt-2 text-neutral-600">Innovation diagnostic platform.</p>
      <div className="mt-6 flex gap-3">
        <Link
          href="/sign-in"
          className="inline-flex items-center justify-center rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-700"
        >
          Sign in
        </Link>
        <Link
          href="/sign-up"
          className="inline-flex items-center justify-center rounded-md border border-neutral-300 bg-white px-4 py-2 text-sm font-medium text-neutral-900 hover:bg-neutral-50"
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
