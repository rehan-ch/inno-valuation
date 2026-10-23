import Image from "next/image";
import Link from "next/link";

const SEGMENTS = [
  { label: "Innovator", text: "Validate your idea before you build." },
  { label: "R&D lead", text: "Prioritise your innovation pipeline." },
  { label: "Procurement", text: "Assess value for money before you buy." },
  { label: "Investor", text: "Screen opportunities by IQ and value." },
];

const FEATURES = [
  {
    accent: "border-t-primary",
    title: "Readiness diagnostic",
    text: "Your team answers 60 questions across the 12 Dimensions of Innovation and agrees a score out of 300, with its band.",
  },
  {
    accent: "border-t-accent",
    title: "Idea IQ and Value for Money",
    text: "Every idea gets an Innovation Quotient out of 100 and a Value for Money figure, so you can rank your whole portfolio.",
  },
  {
    accent: "border-t-primary",
    title: "Built for teams",
    text: "Invite your team, agree answers together, and give your consultant read-only access for exactly as long as you choose.",
  },
];

export default function Home() {
  return (
    <main id="main" className="mx-auto w-full max-w-5xl flex-1 px-4 py-10">
      <header className="flex items-center justify-between">
        <span className="flex items-center gap-2">
          <Image src="/innovaluation-mark.png" alt="" width={32} height={31} />
          <span className="bg-linear-to-r from-primary to-accent bg-clip-text font-serif text-xl font-semibold tracking-tight text-transparent">
            InnoValuation
          </span>
        </span>
        <Link
          href="/sign-in"
          className="inline-flex items-center justify-center rounded-full bg-primary px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-strong"
        >
          Sign in
        </Link>
      </header>

      <section className="mt-14 grid grid-cols-1 items-center gap-10 lg:grid-cols-2">
        <div>
          <p className="inline-flex rounded-full border border-neutral-200 bg-white px-4 py-1.5 text-xs font-medium tracking-[0.2em] text-primary uppercase">
            Innovation intelligence
          </p>
          <h1 className="mt-6 text-4xl font-semibold tracking-tight sm:text-5xl">
            Score every idea on{" "}
            <span className="bg-linear-to-r from-primary to-accent bg-clip-text text-transparent">
              Innovation Quotient
            </span>{" "}
            and Value for Money.
          </h1>
          <p className="mt-5 max-w-lg text-base leading-relaxed text-neutral-600">
            InnoValuation turns fuzzy intuition into informed decisions. Measure how ready your
            organisation is to innovate, score every idea against the 12 Dimensions of Innovation,
            and see what each point of quality costs.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/sign-up"
              className="inline-flex items-center justify-center rounded-full bg-accent px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-accent/85"
            >
              Create an account
            </Link>
            <Link
              href="/sign-in"
              className="inline-flex items-center justify-center rounded-full border border-neutral-300 bg-white px-6 py-2.5 text-sm font-medium text-neutral-900 transition-colors hover:bg-neutral-50"
            >
              Sign in
            </Link>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {SEGMENTS.map((segment) => (
            <div
              key={segment.label}
              className="rounded-2xl border border-neutral-200 bg-white p-4 shadow-sm"
            >
              <p className="text-sm font-medium text-neutral-900">{segment.label}</p>
              <p className="mt-1 text-xs leading-snug text-neutral-600">{segment.text}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-16 grid grid-cols-1 gap-6 md:grid-cols-3">
        {FEATURES.map((feature) => (
          <div
            key={feature.title}
            className={`rounded-2xl border border-neutral-200 border-t-2 bg-white p-6 shadow-sm ${feature.accent}`}
          >
            <h2 className="text-base font-semibold text-neutral-900">{feature.title}</h2>
            <p className="mt-2 text-sm leading-relaxed text-neutral-600">{feature.text}</p>
          </div>
        ))}
      </section>

      <footer className="mt-16 border-t border-neutral-200 pt-6 text-sm text-neutral-500">
        <Link href="/health" className="underline hover:text-neutral-900">
          System health
        </Link>
      </footer>
    </main>
  );
}
