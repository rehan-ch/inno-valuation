"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

import { MeProvider } from "@/components/app/me-context";
import { OrgSwitcher } from "@/components/app/OrgSwitcher";
import { Alert } from "@/components/ui/Alert";
import { Button, buttonClass } from "@/components/ui/Button";
import { Loading } from "@/components/ui/Loading";
import { signOut } from "@/lib/api/auth";
import { ApiError, setUnauthorizedHandler } from "@/lib/api/client";
import { getMe } from "@/lib/api/me";
import type { MeOut } from "@/lib/api/types";
import { signInHref } from "@/lib/next-param";
import { activeMembership, canManage } from "@/lib/roles";

type State =
  | { kind: "loading" }
  | { kind: "ready"; me: MeOut }
  | { kind: "error"; message: string };

/** A main-navigation tab that marks the page it is on for styling and screen readers. */
function NavLink({ href, children }: { href: string; children: ReactNode }) {
  const pathname = usePathname();
  const current = pathname === href || pathname.startsWith(`${href}/`);
  return (
    <Link
      href={href}
      aria-current={current ? "page" : undefined}
      className={`-mb-px inline-flex h-10 shrink-0 items-center border-b-2 px-1 text-sm whitespace-nowrap transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${
        current
          ? "border-primary font-medium text-neutral-900"
          : "border-transparent text-neutral-600 hover:border-neutral-300 hover:text-neutral-900"
      }`}
    >
      {children}
    </Link>
  );
}

/** The signed-in frame: loads /me, sends visitors without a session to sign in, and
 * shows the navigation with the organisation switcher. */
export function AppShell({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>({ kind: "loading" });
  const router = useRouter();
  const header = useRef<HTMLElement>(null);
  const ready = state.kind === "ready";

  // Sticky page panels sit just below the header (top: var(--app-header-h)), and the
  // header grows when its navigation wraps, so its real height is published here.
  useEffect(() => {
    const element = header.current;
    if (!element) return;
    const publish = () =>
      document.documentElement.style.setProperty(
        "--app-header-h",
        `${element.offsetHeight}px`,
      );
    publish();
    const observer = new ResizeObserver(publish);
    observer.observe(element);
    return () => observer.disconnect();
  }, [ready]);

  const load = useCallback(async () => {
    try {
      const me = await getMe();
      setState({ kind: "ready", me });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.replace(signInHref());
        return;
      }
      setState({
        kind: "error",
        message: err instanceof ApiError ? err.message : "Something went wrong.",
      });
    }
  }, [router]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch on mount; state is set only once the response arrives
    void load();
  }, [load]);

  // Once signed in, a 401 from any later call (the session expired or was ended elsewhere)
  // sends the visitor to sign in and back here afterwards. The initial load above handles
  // its own 401, so the handler is registered only once the shell is ready.
  useEffect(() => {
    if (!ready) return;
    setUnauthorizedHandler(() => router.replace(signInHref()));
    return () => setUnauthorizedHandler(null);
  }, [ready, router]);

  async function handleSignOut() {
    try {
      await signOut();
    } catch {
      // Go to sign-in anyway: its page loads /me, so a session that survived a
      // failed sign-out call shows up instead of being silently kept.
    }
    router.push("/sign-in");
  }

  if (state.kind === "loading") {
    return (
      <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-10">
        <Loading>Loading your account...</Loading>
      </main>
    );
  }

  if (state.kind === "error") {
    return (
      <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-10">
        <Alert tone="error">{state.message}</Alert>
      </main>
    );
  }

  const { me } = state;
  const membership = activeMembership(me);

  return (
    <MeProvider
      value={{
        me,
        update: (next) => setState({ kind: "ready", me: next }),
        refresh: load,
      }}
    >
      <header ref={header} className="sticky top-0 z-30 border-b border-neutral-200 bg-white">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-4 pt-3">
          <Link
            href="/dashboard"
            className="flex shrink-0 items-center gap-2 rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
          >
            <Image src="/innovaluation-mark.png" alt="" width={24} height={23} />
            <span className="text-[15px] font-semibold tracking-tight text-neutral-900">
              InnoValuation
            </span>
          </Link>
          <div className="flex min-w-0 items-center gap-2">
            <OrgSwitcher />
            <Link
              href="/organisations/new"
              className={buttonClass("ghost", "sm", "hidden sm:inline-flex")}
            >
              New organisation
            </Link>
            <Button variant="secondary" size="sm" onClick={() => void handleSignOut()}>
              Sign out
            </Button>
          </div>
        </div>
        <nav
          aria-label="Main"
          className="mx-auto flex w-full max-w-6xl flex-wrap gap-x-5 px-4 pt-1"
        >
          <NavLink href="/dashboard">Dashboard</NavLink>
          {(membership || me.consultant_organisations.length > 0) && (
            <NavLink href="/readiness">Readiness</NavLink>
          )}
          {membership && <NavLink href="/team">Team</NavLink>}
          {membership && canManage(membership.role) && (
            <>
              <NavLink href="/organisation">Organisation</NavLink>
              <NavLink href="/consultants">Consultants</NavLink>
            </>
          )}
          {me.consultant_organisations.length > 0 && (
            <NavLink href="/consultant-access">My access</NavLink>
          )}
          <NavLink href="/account">Account</NavLink>
          <Link
            href="/organisations/new"
            className="-mb-px inline-flex h-10 shrink-0 items-center border-b-2 border-transparent px-1 text-sm whitespace-nowrap text-neutral-600 hover:text-neutral-900 sm:hidden"
          >
            New organisation
          </Link>
        </nav>
      </header>
      <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        {children}
      </main>
    </MeProvider>
  );
}
