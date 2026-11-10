import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { RecordedCall } from "@/test/api";
import { fakeDashboard, fakeMe, fakeTargets, stubApi } from "@/test/api";
import { renderWithMe } from "@/test/me";

import { TargetsPage, describeTargets, targetError } from "./TargetsPage";

vi.mock("next/navigation", async () => (await import("@/test/navigation")).navigationMock());

describe("targetError", () => {
  it("allows a blank box and whole numbers inside the scale's range", () => {
    for (const value of ["", "  ", "5", "25", " 12 "]) {
      expect(targetError(value, { minimum: 5, maximum: 25 })).toBeUndefined();
    }
  });

  it("refuses decimals, words and numbers outside the range", () => {
    expect(targetError("7.5", { minimum: 1, maximum: 10 })).toMatch(/whole number/);
    expect(targetError("high", { minimum: 1, maximum: 10 })).toMatch(/whole number/);
    expect(targetError("-3", { minimum: 1, maximum: 10 })).toMatch(/whole number/);
    expect(targetError("11", { minimum: 1, maximum: 10 })).toBe("From 1 to 10.");
    expect(targetError("4", { minimum: 5, maximum: 25 })).toBe("From 5 to 25.");
  });
});

describe("describeTargets", () => {
  it("names each dimension with its target, or says they were all removed", () => {
    const names = new Map([["customer_journey", "Customer Journey"]]);
    const change = {
      id: "c1",
      scale: "readiness" as const,
      set_at: "2026-11-01T09:00:00Z",
      set_by_name: "Olive Owner",
      targets: { customer_journey: 22, other_key: 9 },
      changed: ["customer_journey"],
    };
    expect(describeTargets(change, names)).toBe("Customer Journey 22, other_key 9");
    expect(describeTargets({ ...change, targets: {} }, names)).toBe("Every target removed.");
  });
});

function form(title: string): HTMLElement {
  return screen.getByRole("heading", { name: title }).closest("section") as HTMLElement;
}

describe("TargetsPage", () => {
  it("shows each scale's targets beside the current score and saves a change", async () => {
    let current = fakeTargets();
    const withGap = fakeDashboard();
    Object.assign(withGap.readiness!.compass.segments[0]!, { target: 22, gap: 2 });
    const calls = stubApi({
      "GET /api/v1/targets": () => current,
      "GET /api/v1/targets/history": [],
      "GET /api/v1/dashboard": withGap,
      "PUT /api/v1/targets/iq": (call: RecordedCall) => {
        const body = call.body as { targets: Record<string, number | null> };
        current = fakeTargets({
          iq: {
            ...current.iq,
            targets: current.iq.targets.map((t) => ({ ...t, target: body.targets[t.key] ?? null })),
            set_at: "2026-11-05T09:00:00Z",
            set_by_name: "Olive Owner",
          },
        });
        return current;
      },
    });
    const user = userEvent.setup();
    renderWithMe(<TargetsPage />, fakeMe());

    const readiness = within(await screen.findByRole("heading", { name: "Readiness targets" }).then(() => form("Readiness targets")));
    expect(readiness.getByLabelText("Target for Customer Journey")).toHaveDisplayValue("22");
    const row = readiness.getByRole("row", { name: /Customer Journey/ });
    expect(row).toHaveTextContent("20 / 25");
    expect(row).toHaveTextContent("2 below target");
    expect(readiness.getByRole("button", { name: "Save targets" })).toBeDisabled();

    const iq = within(form("Idea targets"));
    const field = iq.getByLabelText("Target for Organizational Agility");
    await user.type(field, "12");
    expect(iq.getByText("From 1 to 10.")).toBeInTheDocument();
    expect(iq.getByRole("button", { name: "Save targets" })).toBeDisabled();
    await user.clear(field);
    await user.type(field, "8");
    await user.click(iq.getByRole("button", { name: "Save targets" }));

    expect(await screen.findByText("Idea targets saved.")).toBeInTheDocument();
    const put = calls.find((c) => c.method === "PUT");
    expect(put?.path).toBe("/api/v1/targets/iq");
    const sent = (put?.body as { targets: Record<string, number | null> }).targets;
    expect(sent.organizational_agility).toBe(8);
    expect(sent.customer_journey).toBeNull(); // an empty box means no target
    // The gaps come from the server again after a save; nothing is worked out here.
    expect(calls.filter((c) => c.path === "/api/v1/dashboard")).toHaveLength(2);
  });

  it("is read-only for people who cannot change targets", async () => {
    stubApi({
      "GET /api/v1/targets": fakeTargets({ can_change: false }),
      "GET /api/v1/targets/history": [
        {
          id: "c1",
          scale: "readiness",
          set_at: "2026-11-01T09:00:00Z",
          set_by_name: null,
          targets: { customer_journey: 22 },
          changed: ["customer_journey"],
        },
      ],
      "GET /api/v1/dashboard": fakeDashboard(),
    });
    renderWithMe(<TargetsPage />, fakeMe());

    expect(await screen.findByText("Owners and admins set the targets. You can see them here.")).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save targets" })).not.toBeInTheDocument();
    const history = within(form("Earlier targets"));
    expect(history.getByText("Customer Journey 22")).toBeInTheDocument();
    expect(history.getByText("Someone who has left")).toBeInTheDocument();
  });
});
