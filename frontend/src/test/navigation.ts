// A next/navigation stand-in for component tests:
//   vi.mock("next/navigation", async () => (await import("@/test/navigation")).navigationMock());
import { vi } from "vitest";

export const routerPush = vi.fn();
export const routerReplace = vi.fn();

// One stable object, like the real app router: effects that depend on it must not refire.
const router = {
  push: routerPush,
  replace: routerReplace,
  refresh: vi.fn(),
  back: vi.fn(),
  prefetch: vi.fn(),
};

export function navigationMock() {
  return {
    useRouter: () => router,
    usePathname: () => window.location.pathname,
    useSearchParams: () => new URLSearchParams(window.location.search),
  };
}

/** Points jsdom at a path so code reading window.location sees it. */
export function setLocation(pathAndQueryAndHash: string) {
  window.history.replaceState(null, "", pathAndQueryAndHash);
}
