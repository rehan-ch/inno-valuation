// Renders a component inside a MeProvider, as the app shell would.
import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { vi } from "vitest";

import { MeProvider } from "@/components/app/me-context";
import type { MeOut } from "@/lib/api/types";

export function renderWithMe(ui: ReactNode, me: MeOut) {
  const update = vi.fn();
  const refresh = vi.fn().mockResolvedValue(undefined);
  const result = render(<MeProvider value={{ me, update, refresh }}>{ui}</MeProvider>);
  return { ...result, update, refresh };
}
