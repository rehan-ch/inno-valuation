import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import HealthPage from "./page";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("Health page", () => {
  it("shows a loading state, then the API and database status and version", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ status: "ok", database: "ok", version: "1.2.3" })),
    );

    render(<HealthPage />);

    expect(screen.getByRole("status")).toHaveTextContent("Checking the API");
    expect(await screen.findByTestId("health-api")).toHaveTextContent("OK");
    expect(screen.getByTestId("health-database")).toHaveTextContent("OK");
    expect(screen.getByTestId("health-version")).toHaveTextContent("1.2.3");
  });

  it("shows a database error when the database is down", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ status: "ok", database: "error", version: "1.2.3" })),
    );

    render(<HealthPage />);

    expect(await screen.findByTestId("health-database")).toHaveTextContent("Error");
  });

  it("shows an error state with the backend error code", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({ error: { code: "service_unavailable", message: "Try again soon." } }, 503),
      ),
    );

    render(<HealthPage />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("We could not reach the API.");
    expect(alert).toHaveTextContent("Try again soon.");
    expect(alert).toHaveTextContent("service_unavailable");
  });
});
