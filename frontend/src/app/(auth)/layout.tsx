
"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const AUTH_PAGES: Record<
  string,
  { title: string; subtitle: string }
> = {
  "/sign-in": {
    title: "Welcome back",
    subtitle: "Sign in to continue your innovation journey.",
  },
  "/sign-up": {
    title: "Start innovating",
    subtitle:
      "Create your account and make smarter innovation decisions.",
  },
  "/forgot-password": {
    title: "Forgot password?",
    subtitle:
      "We'll help you regain access to your workspace.",
  },
  "/reset-password": {
    title: "Secure your account",
    subtitle:
      "Choose a new password to regain access to your workspace.",
  },
  "/verify-email": {
    title: "Verify your email",
    subtitle:
      "One final step to secure your innovation workspace.",
  },
};

function Logo({ light = false }: { light?: boolean }) {
  return (
    <Link
      href="/"
      aria-label="InnoValuation home"
      className="inline-flex w-fit items-center gap-2.5 rounded-md focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#DAB56D]"
    >
      <Image
        src="/innovaluation-mark.png"
        alt=""
        width={40}
        height={40}
        priority
        className="size-10 shrink-0 object-contain"
      />

      <span
        className={`text-xl font-bold tracking-tight ${light ? "text-white" : "text-[#10243B]"
          }`}
      >
        InnoValuation
      </span>
    </Link>
  );
}

function BrandPanel() {
  return (
    <aside className="relative hidden min-w-0 flex-col overflow-hidden bg-[#10243B] px-10 py-8 text-white lg:flex lg:w-[53%] xl:px-16 2xl:px-20">
      {/* Subtle geometry, without colour gradients. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-28 top-1/4 size-80 rounded-full border border-white/[0.055]"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-14 top-1/3 size-56 rounded-full border border-white/[0.055]"
      />

      <div className="relative z-10 shrink-0">
        <Logo light />
      </div>

      <div className="relative z-10 my-auto max-w-[610px] py-5">
        <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/[0.055] px-3.5 py-2 text-[10px] font-semibold tracking-[0.16em] text-[#E2BC77]">
          <span className="size-1.5 rounded-full bg-[#DAB56D]" />
          INNOVATION INTELLIGENCE
        </div>

        <p className="max-w-[590px] text-[clamp(2rem,3.2vw,3.5rem)] leading-[1.12] font-semibold tracking-[-0.035em] text-balance">
          Great ideas deserve{" "}
          <span className="text-[#DAB56D]">
            measurable impact.
          </span>
        </p>

        <p className="mt-5 max-w-[510px] text-[15px] leading-7 text-[#C5D0DC]">
          Understand your innovation potential, evaluate
          opportunities with confidence, and turn ambitious
          ideas into meaningful outcomes.
        </p>

        <div className="mt-7 max-w-[520px] rounded-2xl border border-white/10 bg-[#1B3452] p-5 shadow-[0_20px_45px_rgba(0,0,0,0.12)]">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-[10px] font-semibold tracking-[0.12em] text-[#AEBFD0]">
                INNOVATION FRAMEWORK
              </p>
              <p className="mt-1.5 text-lg font-semibold text-white">
                Discover your potential
              </p>
            </div>

            <span className="shrink-0 rounded-lg border border-[#DAB56D]/25 bg-[#DAB56D]/10 px-3 py-2 text-xs font-semibold text-[#E2BC77]">
              12 dimensions
            </span>
          </div>

          <div
            className="mt-5 grid grid-cols-12 gap-1.5"
            aria-hidden="true"
          >
            {Array.from({ length: 12 }, (_, index) => (
              <span
                key={index}
                className={`h-2 rounded-full ${index < 8
                  ? "bg-[#DAB56D]"
                  : "bg-white/15"
                  }`}
              />
            ))}
          </div>

          <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-xs text-[#C5D0DC]">
            <span>Innovation readiness</span>
            <span>Idea evaluation</span>
            <span>Team alignment</span>
          </div>
        </div>

        <p className="mt-6 text-sm font-medium text-[#E2BC77]">
          Think bigger. Measure smarter. Innovate confidently.
        </p>
      </div>

      <div className="relative z-10 flex shrink-0 items-center justify-between gap-3 text-xs text-[#9EADBF]">
        <span>Innovation · Growth · Valuation</span>
        <span>InnoValuation</span>
      </div>
    </aside>
  );
}

function MobileBrand() {
  return (
    <header className="shrink-0 border-b border-white/10 bg-[#10243B] px-5 py-3.5 text-white sm:px-8 lg:hidden">
      <div className="flex items-center justify-between gap-3">
        <Logo light />

        <span className="shrink-0 rounded-full border border-[#DAB56D]/25 px-2.5 py-1 text-[10px] font-semibold text-[#E2BC77]">
          INNOVATE
        </span>
      </div>

      <p className="mt-1 text-[11px] text-[#C5D0DC]">
        Great ideas deserve measurable impact.
      </p>
    </header>
  );
}

function AuthPanel({
  children,
  pathname,
}: {
  children: ReactNode;
  pathname: string;
}) {
  const heading = AUTH_PAGES[pathname] ?? {
    title: "Welcome back",
    subtitle:
      "Sign in to continue your innovation journey.",
  };

  return (
    <section className="flex min-w-0 flex-1 flex-col justify-start bg-white px-5 pt-7 pb-5 sm:justify-center sm:px-10 sm:py-8 lg:px-10 xl:px-16">
      <div className="mx-auto w-full max-w-[430px]">
        <div className="mb-5 sm:mb-6">
          <div className="hidden lg:block">
            <Logo />
          </div>

          <div className="lg:mt-9">
            <p className="text-[10px] font-bold tracking-[0.15em] text-[#315779]">
              YOUR INNOVATION WORKSPACE
            </p>

            {/* The page's h1 on every width; the forms' own headings are h2. */}
            <h1 className="mt-2 text-[28px] leading-tight font-semibold tracking-tight text-[#10243B] sm:text-3xl">
              {heading.title}
            </h1>

            <p className="mt-2 text-sm leading-6 text-[#64748B]">
              {heading.subtitle}
            </p>
          </div>
        </div>

        {children}

        <p className="mt-6 text-center text-[11px] text-[#94A3B8]">
          Innovation · Growth · Valuation
        </p>
      </div>
    </section>
  );
}

export default function AuthLayout({
  children,
}: {
  children: ReactNode;
}) {
  const pathname = usePathname();

  const premium = Object.prototype.hasOwnProperty.call(
    AUTH_PAGES,
    pathname,
  );

  if (!premium) {
    return (
      <main
        id="main"
        className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-4 py-10"
      >
        <div className="mb-6 flex justify-center">
          <Logo />
        </div>

        <div className="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm">
          {children}
        </div>
      </main>
    );
  }

  return (
    <main
      id="main"
      className="iv-auth-layout flex min-h-dvh w-full flex-col bg-white lg:h-dvh lg:min-h-0 lg:flex-row lg:overflow-y-auto"
    >
      <MobileBrand />
      <BrandPanel />
      <AuthPanel pathname={pathname}>
        {children}
      </AuthPanel>
    </main>
  );
}
