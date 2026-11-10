import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { errorResponse, fakeAuditEvent, fakeMe, stubApi } from "@/test/api";
import { renderWithMe } from "@/test/me";

import { ActivityPage } from "./ActivityPage";

vi.mock("next/navigation", async () => (await import("@/test/navigation")).navigationMock());

const FILTERS = {
  actions: [
    { action: "idea.created", label: "Idea added" },
    { action: "iq.confirmed", label: "Idea scores confirmed" },
  ],
  actors: [{ id: "11111111-1111-1111-1111-111111111111", name: "Olive Owner" }],
};

describe("ActivityPage", () => {
  it("lists who did what, with the method version and the AI model, and filters by action", async () => {
    const added = fakeAuditEvent({
      id: "e2",
      action: "idea.created",
      action_label: "Idea added",
      detail: null,
      question_set_version: null,
      ai_model: null,
      actor_name: null,
    });
    const calls = stubApi({
      "GET /api/v1/audit/filters": FILTERS,
      "GET /api/v1/audit": () => {
        const asked = new URL(String(vi.mocked(fetch).mock.lastCall?.[0])).searchParams;
        const events = asked.get("action") === "idea.created" ? [added] : [fakeAuditEvent(), added];
        return { events, next_before: null };
      },
    });
    const user = userEvent.setup();
    renderWithMe(<ActivityPage />, fakeMe());

    const table = within(await screen.findByRole("table", { name: "Activity log, newest first" }));
    const confirmed = table.getByRole("row", { name: /Idea scores confirmed/ });
    expect(confirmed).toHaveTextContent("Olive Owner");
    expect(confirmed).toHaveTextContent("Same-day delivery");
    expect(confirmed).toHaveTextContent("Changed from the AI's proposal: Organizational Agility.");
    expect(confirmed).toHaveTextContent("Question set version 1 · AI model claude-opus-5-5");
    expect(table.getByRole("row", { name: /Idea added/ })).toHaveTextContent("Someone who has left");

    // Read-only: no control changes or removes an entry.
    expect(screen.queryByRole("button", { name: /delete|remove|edit/i })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Export as CSV" })).toHaveAttribute(
      "href",
      expect.stringMatching(/\/api\/v1\/audit\/export$/),
    );

    await user.selectOptions(screen.getByLabelText("Action"), "Idea added");
    expect(await screen.findByRole("button", { name: "Clear filters" })).toBeInTheDocument();
    expect(screen.queryByRole("row", { name: /Idea scores confirmed/ })).not.toBeInTheDocument();
    expect(calls.at(-1)?.path).toBe("/api/v1/audit");
    expect(screen.getByRole("link", { name: "Export as CSV" })).toHaveAttribute(
      "href",
      expect.stringMatching(/\/audit\/export\?action=idea\.created$/),
    );
  });

  it("loads earlier entries with the cursor the server gave", async () => {
    let page = 0;
    stubApi({
      "GET /api/v1/audit/filters": FILTERS,
      "GET /api/v1/audit": () => {
        page += 1;
        return page === 1
          ? { events: [fakeAuditEvent({ id: "new" })], next_before: "cursor-1" }
          : {
              events: [fakeAuditEvent({ id: "old", action_label: "Idea added", detail: null })],
              next_before: null,
            };
      },
    });
    const user = userEvent.setup();
    renderWithMe(<ActivityPage />, fakeMe());

    await user.click(await screen.findByRole("button", { name: "Show earlier entries" }));
    expect(await screen.findByRole("row", { name: /Idea added/ })).toBeInTheDocument();
    expect(screen.getByRole("row", { name: /Idea scores confirmed/ })).toBeInTheDocument();
    expect(new URL(String(vi.mocked(fetch).mock.lastCall?.[0])).searchParams.get("before")).toBe("cursor-1");
    expect(screen.queryByRole("button", { name: "Show earlier entries" })).not.toBeInTheDocument();
  });

  it("tells someone without the permission why the log is not shown", async () => {
    stubApi({
      "GET /api/v1/audit/filters": errorResponse("forbidden", "You do not have permission to do this.", 403),
      "GET /api/v1/audit": errorResponse("forbidden", "You do not have permission to do this.", 403),
    });
    renderWithMe(<ActivityPage />, fakeMe());

    expect(await screen.findByText("Only owners and admins can see the activity log.")).toBeInTheDocument();
  });
});
