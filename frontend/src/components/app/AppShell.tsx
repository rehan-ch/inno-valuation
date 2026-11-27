
"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";
import {
  ArrowUpRight,
  BriefcaseBusiness,
  Building2,
  ClipboardCheck,
  LayoutDashboard,
  LogOut,
  Menu,
  Plus,
  ShieldCheck,
  UserRound,
  UsersRound,
  X,
  History,
  Lightbulb,
  Target,
} from "lucide-react";

import { MeProvider } from "@/components/app/me-context";
import { OrgSwitcher } from "@/components/app/OrgSwitcher";
import { Alert } from "@/components/ui/Alert";
import { Loading } from "@/components/ui/Loading";
import { signOut } from "@/lib/api/auth";
import {
  ApiError,
  setUnauthorizedHandler,
} from "@/lib/api/client";
import { signInHref } from "@/lib/next-param";
import { getMe } from "@/lib/api/me";
import type { MeOut } from "@/lib/api/types";
import { activeMembership, canManage } from "@/lib/roles";

type State =
  | { kind: "loading" }
  | { kind: "ready"; me: MeOut }
  | { kind: "error"; message: string };

type NavItem = {
  href: string;
  label: string;
  icon: typeof LayoutDashboard;
};

function WorkspaceLink({
  item,
  mobile = false,
  onNavigate,
}: {
  item: NavItem;
  mobile?: boolean;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  const active =
    pathname === item.href ||
    pathname.startsWith(`${item.href}/`);

  const Icon = item.icon;

  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      // On narrower desktops the header shows only the icon; the tooltip names it.
      title={mobile ? undefined : item.label}
      onClick={onNavigate}
      className={[
        "iv-nav-link",
        active ? "iv-nav-active" : "",
        mobile ? "iv-nav-mobile-link" : "",
      ].filter(Boolean).join(" ")}
    >
      <Icon size={18} strokeWidth={1.7} aria-hidden="true" />
      <span>{item.label}</span>

      {mobile && (
        <span className="iv-mobile-nav-end" aria-hidden="true">
          {active ? (
            <span className="iv-nav-current-dot" />
          ) : (
            <ArrowUpRight size={15} />
          )}
        </span>
      )}
    </Link>
  );
}

function OrganisationControl() {
  return (
    <div className="iv-org-control">
      <OrgSwitcher />
    </div>
  );
}

export function AppShell({
  children,
}: {
  children: ReactNode;
}) {
  const [state, setState] = useState<State>({
    kind: "loading",
  });
  const [mobileOpen, setMobileOpen] = useState(false);

  const router = useRouter();
  const pathname = usePathname();
  const header = useRef<HTMLElement>(null);

  const ready = state.kind === "ready";

  // Keep sticky page content aligned below the actual header.
  useEffect(() => {
    const element = header.current;
    if (!element) return;

    const publish = () => {
      document.documentElement.style.setProperty(
        "--app-header-h",
        `${element.offsetHeight}px`,
      );
    };

    publish();

    if (typeof ResizeObserver === "undefined") return;

    const observer = new ResizeObserver(publish);
    observer.observe(element);

    return () => observer.disconnect();
  }, [ready]);

  // Preserve the existing authentication and /me workflow.
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
        message:
          err instanceof ApiError
            ? err.message
            : "Something went wrong.",
      });
    }
  }, [router]);

  useEffect(() => {
    void Promise.resolve().then(() => load());
  }, [load]);

  // Redirect to sign-in when an authenticated session expires.
  useEffect(() => {
    if (!ready) return;

    setUnauthorizedHandler(() => router.replace(signInHref()));

    return () => setUnauthorizedHandler(null);
  }, [ready, router]);

  // Allow users to dismiss the mobile menu with Escape.
  useEffect(() => {
    if (!mobileOpen) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMobileOpen(false);
      }
    };

    document.addEventListener("keydown", onKeyDown);
    return () =>
      document.removeEventListener("keydown", onKeyDown);
  }, [mobileOpen]);

  async function handleSignOut() {
    setMobileOpen(false);

    try {
      await signOut();
    } catch {
      // Preserve the existing sign-out fallback.
    }

    router.push("/sign-in");
  }

  if (state.kind === "loading") {
    return (
      <main
        id="main"
        className="mx-auto w-full max-w-5xl flex-1 px-4 py-10"
      >
        <Loading>Loading your account...</Loading>
      </main>
    );
  }

  if (state.kind === "error") {
    return (
      <main
        id="main"
        className="mx-auto w-full max-w-5xl flex-1 px-4 py-10"
      >
        <Alert tone="error">{state.message}</Alert>
      </main>
    );
  }

  const { me } = state;
  const membership = activeMembership(me);
  const manager =
    !!membership && canManage(membership.role);

  const navItems: NavItem[] = [
    {
      href: "/dashboard",
      label: "Dashboard",
      icon: LayoutDashboard,
    },
    ...(
      membership || me.consultant_organisations.length > 0
        ? [
          {
            href: "/readiness",
            label: "Readiness",
            icon: ClipboardCheck,
          },
          ...(me.ai_enabled
            ? [
              {
                href: "/ideas",
                label: "Ideas",
                icon: Lightbulb,
              },
            ]
            : []),
          {
            href: "/targets",
            label: "Targets",
            icon: Target,
          },
          {
            href: "/history",
            label: "History",
            icon: History,
          },
        ]
        : []
    ),
    ...(membership
      ? [{
        href: "/team",
        label: "Team",
        icon: UsersRound,
      }]
      : []),
    ...(manager
      ? [
        {
          href: "/organisation",
          label: "Organisation",
          icon: Building2,
        },
        {
          href: "/consultants",
          label: "Consultants",
          icon: BriefcaseBusiness,
        },
      ]
      : []),
    ...(me.consultant_organisations.length > 0
      ? [{
        href: "/consultant-access",
        label: "My access",
        icon: ShieldCheck,
      }]
      : []),
    {
      href: "/account",
      label: "Account",
      icon: UserRound,
    },
  ];

  const initial =
    me.name.trim().charAt(0).toUpperCase() || "U";

  const accountActive =
    pathname === "/account";

  return (
    <MeProvider
      value={{
        me,
        update: (next) =>
          setState({ kind: "ready", me: next }),
        refresh: load,
      }}
    >
      <div className="iv-workspace">
        <header
          ref={header}
          className="iv-app-header"
        >
          <div className="iv-header-inner">
            <Link
              href="/dashboard"
              className="iv-brand"
              aria-label="InnoValuation dashboard"
              onClick={() => setMobileOpen(false)}
            >
              <span className="iv-brand-mark">
                <Image
                  src="/innovaluation-mark.png"
                  alt=""
                  width={38}
                  height={38}
                  priority
                  className="object-contain"
                />
              </span>

              <span className="iv-brand-name">
                Inno<span>Valuation</span>
              </span>
            </Link>

            <nav
              aria-label="Main navigation"
              className="iv-desktop-nav"
            >
              {/* Account is the avatar beside the actions; listing it here too would
                  cost the room the other links need. The mobile menu keeps it. */}
              {navItems
                .filter((item) => item.href !== "/account")
                .map((item) => (
                  <WorkspaceLink
                    key={item.href}
                    item={item}
                  />
                ))}
            </nav>

            <div className="iv-header-actions iv-header-actions-fixed">
              <div className="iv-desktop-org">
                <OrganisationControl />
              </div>

              <Link
                href="/organisations/new"
                className="iv-header-create"
                aria-label="New organisation"
                title="Create organisation"
              >
                <Plus size={18} aria-hidden="true" />
              </Link>

              <button
                type="button"
                className="iv-desktop-signout"
                onClick={() => void handleSignOut()}
              >
                <LogOut size={16} aria-hidden="true" />
                <span>Sign out</span>
              </button>

              <Link
                href="/account"
                className={[
                  "iv-account-avatar",
                  accountActive ? "iv-avatar-active" : "",
                ].filter(Boolean).join(" ")}
                aria-label="Account settings"
                aria-current={accountActive ? "page" : undefined}
                title={me.name}
                onClick={() => setMobileOpen(false)}
              >
                {initial}
              </Link>

              <button
                type="button"
                className="iv-mobile-toggle"
                aria-label={
                  mobileOpen ? "Close menu" : "Open menu"
                }
                aria-expanded={mobileOpen}
                aria-controls="iv-mobile-menu"
                onClick={() =>
                  setMobileOpen((value) => !value)
                }
              >
                {mobileOpen
                  ? <X size={22} aria-hidden="true" />
                  : <Menu size={22} aria-hidden="true" />}
              </button>
            </div>
          </div>

          {mobileOpen && (
            <div
              id="iv-mobile-menu"
              className="iv-mobile-menu"
            >
              <div className="iv-mobile-menu-inner">
                <div className="iv-mobile-profile">
                  <div className="iv-mobile-profile-avatar">
                    {initial}
                  </div>

                  <div className="min-w-0">
                    <p className="iv-profile-name">
                      {me.name}
                    </p>
                    <p className="iv-profile-email">
                      {me.email}
                    </p>
                  </div>
                </div>

                <div className="iv-mobile-org">
                  <span className="iv-mobile-caption">
                    YOUR WORKSPACE
                  </span>
                  <OrganisationControl />
                </div>

                <span className="iv-mobile-caption iv-menu-caption">
                  MAIN MENU
                </span>

                <nav
                  aria-label="Mobile navigation"
                  className="iv-mobile-links"
                >
                  {navItems.map((item) => (
                    <WorkspaceLink
                      key={item.href}
                      item={item}
                      mobile
                      onNavigate={() => setMobileOpen(false)}
                    />
                  ))}
                </nav>

                <div className="iv-mobile-footer">
                  <Link
                    href="/organisations/new"
                    className="iv-mobile-secondary"
                    onClick={() => setMobileOpen(false)}
                  >
                    <Plus size={18} aria-hidden="true" />
                    <span>New organisation</span>
                    <ArrowUpRight
                      size={15}
                      className="ml-auto"
                      aria-hidden="true"
                    />
                  </Link>

                  <button
                    type="button"
                    className="iv-mobile-secondary"
                    onClick={() => void handleSignOut()}
                  >
                    <LogOut size={18} aria-hidden="true" />
                    <span>Sign out</span>
                  </button>
                </div>

                <p className="iv-menu-footnote">
                  INNOVATION · GROWTH · VALUATION
                </p>
              </div>
            </div>
          )}
        </header>

        {mobileOpen && (
          <button
            type="button"
            className="iv-mobile-backdrop"
            aria-label="Close menu"
            onClick={() => setMobileOpen(false)}
          />
        )}

        <main id="main" className="iv-main">
          {children}
        </main>
      </div>
    </MeProvider>
  );
}
