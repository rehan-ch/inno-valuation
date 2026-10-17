"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";

import { MeProvider } from "@/components/app/me-context";
import { OrgSwitcher } from "@/components/app/OrgSwitcher";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Loading } from "@/components/ui/Loading";
import { signOut } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import { getMe } from "@/lib/api/me";
import type { MeOut } from "@/lib/api/types";
import { activeMembership, canManage } from "@/lib/roles";

type State =
  | { kind: "loading" }
  | { kind: "ready"; me: MeOut }
  | { kind: "error"; message: string };

/** A main-navigation link that marks the page it is on for styling and screen readers. */
function NavLink({ href, children }: { href: string; children: ReactNode }) {
  const current = usePathname() === href;
  return (
    <Link
      href={href}
      aria-current={current ? "page" : undefined}
      className={
        current ? "font-medium text-neutral-900" : "hover:text-neutral-900 hover:underline"
      }
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

  const load = useCallback(async () => {
    try {
      const me = await getMe();
      setState({ kind: "ready", me });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        const next = window.location.pathname + window.location.search;
        router.replace(`/sign-in?next=${encodeURIComponent(next)}${window.location.hash}`);
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
      <main id="main" className="mx-auto w-full max-w-5xl flex-1 px-4 py-10">
        <Loading>Loading your account...</Loading>
      </main>
    );
  }

  if (state.kind === "error") {
    return (
      <main id="main" className="mx-auto w-full max-w-5xl flex-1 px-4 py-10">
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
      <header className="border-b border-neutral-200 bg-white">
        <div className="mx-auto flex w-full max-w-5xl flex-wrap items-center gap-x-6 gap-y-3 px-4 py-3">
          <Link href="/team" className="text-base font-semibold text-neutral-900">
            InnoValuation
          </Link>
          <nav aria-label="Main" className="flex items-center gap-4 text-sm text-neutral-700">
            {membership && <NavLink href="/team">Team</NavLink>}
            {membership && canManage(membership.role) && (
              <NavLink href="/consultants">Consultants</NavLink>
            )}
            {me.consultant_organisations.length > 0 && (
              <NavLink href="/consultant-access">My access</NavLink>
            )}
            <NavLink href="/account">Account</NavLink>
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <OrgSwitcher />
            <Link
              href="/organisations/new"
              className="text-sm text-neutral-700 hover:text-neutral-900 hover:underline"
            >
              New organisation
            </Link>
            <Button variant="secondary" onClick={() => void handleSignOut()}>
              Sign out
            </Button>
          </div>
        </div>
      </header>
      <main id="main" className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">
        {children}
      </main>
    </MeProvider>
  );
}
