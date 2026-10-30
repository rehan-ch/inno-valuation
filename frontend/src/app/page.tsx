import Image from "next/image";
import Link from "next/link";

import { buttonClass } from "@/components/ui/Button";

const SEGMENTS = [
  { label: "Innovators", text: "Validate an idea before you build it." },
  { label: "R&D leads", text: "Rank the pipeline on one scale." },
  { label: "Procurement", text: "Check value for money before you buy." },
  { label: "Investors", text: "Screen opportunities by IQ and value." },
];

const FEATURES = [
  {
    title: "Readiness diagnostic",
    text: "Your team answers 60 questions across the 12 Dimensions of Innovation and agrees a score out of 300, with its band and the dimensions to work on first.",
  },
  {
    title: "Idea IQ and Value for Money",
    text: "Every idea gets an Innovation Quotient out of 100 and a Value for Money figure, so the whole portfolio can be compared on the same terms.",
  },
  {
    title: "Built for teams",
    text: "Invite your team, agree answers together, and give a consultant read-only access for exactly as long as you choose.",
  },
];

export default function Home() {
  return (
    <div className="flex flex-1 flex-col">
      <header className="border-b border-neutral-200 bg-white">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-3">
          <span className="flex items-center gap-2">
            <Image src="/innovaluation-mark.png" alt="" width={24} height={23} />
            <span className="text-[15px] font-semibold tracking-tight text-neutral-900">
              InnoValuation
            </span>
          </span>
          <nav aria-label="Account" className="flex items-center gap-2">
            <Link href="/sign-in" className={buttonClass("ghost", "sm")}>
              Sign in
            </Link>
            <Link href="/sign-up" className={buttonClass("primary", "sm")}>
              Create an account
            </Link>
          </nav>
        </div>
      </header>

      <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4">
        <section className="grid grid-cols-1 gap-10 border-b border-neutral-200 py-16 lg:grid-cols-12 lg:py-20">
          <div className="lg:col-span-7">
            <p className="text-sm font-medium text-primary">The 12 Dimensions of Innovation</p>
            <h1 className="mt-3 max-w-xl text-3xl font-semibold text-neutral-900 sm:text-4xl">
              Measure how ready your organisation is to innovate, and what each idea is worth.
            </h1>
            <p className="mt-5 max-w-xl text-base leading-relaxed text-neutral-600">
              InnoValuation scores an organisation&apos;s readiness out of 300 and every idea on
              Innovation Quotient and Value for Money, using the method from the book. The numbers
              come from your team&apos;s answers, not from a model&apos;s opinion.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/sign-up" className={buttonClass("primary")}>
                Create an account
              </Link>
              <Link href="/sign-in" className={buttonClass("secondary")}>
                Sign in
              </Link>
            </div>
          </div>
          <dl className="grid grid-cols-1 gap-px overflow-hidden rounded-lg border border-neutral-200 bg-neutral-200 sm:grid-cols-2 lg:col-span-5">
            {SEGMENTS.map((segment) => (
              <div key={segment.label} className="bg-white p-5">
                <dt className="text-sm font-medium text-neutral-900">{segment.label}</dt>
                <dd className="mt-1 text-sm text-neutral-600">{segment.text}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section aria-label="What it does" className="grid grid-cols-1 gap-10 py-16 md:grid-cols-3">
          {FEATURES.map((feature, index) => (
            <div key={feature.title} className="border-t-2 border-neutral-900 pt-5">
              <p className="text-xs font-medium text-neutral-500 tabular-nums">
                {String(index + 1).padStart(2, "0")}
              </p>
              <h2 className="mt-2 text-base font-semibold text-neutral-900">{feature.title}</h2>
              <p className="mt-2 text-sm leading-relaxed text-neutral-600">{feature.text}</p>
            </div>
          ))}
        </section>
      </main>

      <footer className="border-t border-neutral-200">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-6 text-sm text-neutral-500">
          <span>InnoValuation</span>
          <Link href="/health" className="hover:text-neutral-900 hover:underline">
            System health
          </Link>
        </div>
      </footer>
    </div>
  );
}
