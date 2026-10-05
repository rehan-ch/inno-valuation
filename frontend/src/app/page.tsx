import Link from "next/link";

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-4 py-10">
      <h1 className="text-3xl font-semibold">InnoValuation</h1>
      <p className="mt-2 text-neutral-600">Innovation diagnostic platform.</p>
      <p className="mt-6 text-sm">
        <Link href="/health" className="underline">
          Check system health
        </Link>
      </p>
    </main>
  );
}
