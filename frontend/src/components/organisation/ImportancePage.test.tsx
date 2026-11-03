import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { RecordedCall } from "@/test/api";
import { fakeMe, fakeWeights, fakeWeightsChange, stubApi } from "@/test/api";
import { renderWithMe } from "@/test/me";

import { ImportancePage, describeChange, weightError } from "./ImportancePage";

vi.mock("next/navigation", async () =>
  (await import("@/test/navigation")).navigationMock(),
);

const LIMITS = { minimum: 0, maximum: 1000, max_decimal_places: 6 };

describe("weightError", () => {
  it("accepts whole numbers and decimals inside the limits", () => {
    for (const value of ["0", "1", "2.5", " 1000 ", "0.123456", "1.500000"]) {
      expect(weightError(value, LIMITS)).toBeUndefined();
    }
  });

  it("refuses words, negatives, too many decimals and values above the maximum", () => {
    expect(weightError("lots", LIMITS)).toMatch(/number/);
    expect(weightError("-1", LIMITS)).toMatch(/number/);
    expect(weightError("1001", LIMITS)).toMatch(/0 to 1000/);
    expect(weightError("0.1234567", LIMITS)).toMatch(/6 decimal/);
  });
});

describe("ImportancePage", () => {
  it("shows equal importance and saves a change", async () => {
    let current = fakeWeights();
    const calls = stubApi({
      "GET /api/v1/weights": () => current,
      "GET /api/v1/weights/history": () =>
        current.custom ? [fakeWeightsChange()] : [],
      "PUT /api/v1/weights": (call: RecordedCall) => {
        const body = call.body as { weights: Record<string, string> };
        current = fakeWeights(body.weights, {
          set_at: "2026-11-03T09:00:00Z",
          set_by_name: "Olive Owner",
        });
        return current;
      },
    });
    const user = userEvent.setup();
    renderWithMe(<ImportancePage />, fakeMe());

    expect(
      await screen.findByText("Every dimension counts equally"),
    ).toBeInTheDocument();
    expect(screen.getByText("No changes yet.")).toBeInTheDocument();
    const field = screen.getByLabelText("Data Intelligence importance");
    expect(field).toHaveDisplayValue("1");
    expect(
      screen.getByRole("button", { name: "Reset to equal importance" }),
    ).toBeDisabled();

    await user.clear(field);
    await user.type(field, "3");
    await user.click(screen.getByRole("button", { name: "Save importance" }));

    expect(await screen.findByText("Saved.")).toBeInTheDocument();
    const put = calls.find((c) => c.method === "PUT");
    expect(put?.body).toMatchObject({
      weights: { data_intelligence: "3", customer_journey: "1" },
    });
    expect(
      Object.keys((put?.body as { weights: object }).weights),
    ).toHaveLength(12);
    expect(
      await screen.findByText("Custom importance is active"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Last changed .* by Olive Owner/),
    ).toBeInTheDocument();
    expect(screen.getByText("Data Intelligence 3")).toBeInTheDocument(); // the history
    expect(
      screen.getByRole("button", { name: "Reset to equal importance" }),
    ).toBeEnabled();
  });

  it("refuses a bad value without calling the server", async () => {
    const calls = stubApi({
      "GET /api/v1/weights": fakeWeights(),
      "GET /api/v1/weights/history": [],
    });
    const user = userEvent.setup();
    renderWithMe(<ImportancePage />, fakeMe());

    const field = await screen.findByLabelText("Brand Magnetism importance");
    await user.clear(field);
    await user.type(field, "1001");
    await user.click(screen.getByRole("button", { name: "Save importance" }));

    expect(await screen.findByText("From 0 to 1000.")).toBeInTheDocument();
    expect(calls.some((c) => c.method === "PUT")).toBe(false);
  });

  it("resets to equal importance", async () => {
    let current = fakeWeights(
      { brand_magnetism: "4" },
      { set_at: "2026-11-03T09:00:00Z" },
    );
    const calls = stubApi({
      "GET /api/v1/weights": () => current,
      "GET /api/v1/weights/history": [
        fakeWeightsChange({ weights: { brand_magnetism: "4" } }),
      ],
      "POST /api/v1/weights/reset": () => {
        current = fakeWeights();
        return current;
      },
    });
    const user = userEvent.setup();
    renderWithMe(<ImportancePage />, fakeMe());

    expect(
      await screen.findByText("Custom importance is active"),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("Brand Magnetism importance"),
    ).toHaveDisplayValue("4");
    await user.click(
      screen.getByRole("button", { name: "Reset to equal importance" }),
    );

    expect(
      await screen.findByText("Every dimension counts equally again."),
    ).toBeInTheDocument();
    expect(
      calls.some((c) => c.method === "POST" && c.path.endsWith("/reset")),
    ).toBe(true);
    expect(
      screen.getByLabelText("Brand Magnetism importance"),
    ).toHaveDisplayValue("1");
  });

  it("is read-only for someone who cannot change it", async () => {
    stubApi({
      "GET /api/v1/weights": fakeWeights(
        { data_intelligence: "3" },
        { can_change: false },
      ),
      "GET /api/v1/weights/history": [fakeWeightsChange()],
    });
    renderWithMe(<ImportancePage />, fakeMe());

    expect(
      await screen.findByText("Custom importance is active"),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("Data Intelligence importance"),
    ).toBeDisabled();
    expect(
      screen.getByText("Only an owner or admin can change the importance."),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Save importance" }),
    ).not.toBeInTheDocument();
  });
});

describe("describeChange", () => {
  it("names the dimensions that differ from 1", () => {
    const names = new Map([["data_intelligence", "Data Intelligence"]]);
    expect(describeChange(fakeWeightsChange(), names)).toBe(
      "Data Intelligence 3",
    );
    expect(describeChange(fakeWeightsChange({ custom: false }), names)).toBe(
      "Every dimension counts equally.",
    );
  });
});
