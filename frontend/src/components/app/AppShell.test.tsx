import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getJson } from "@/lib/api/client";
import { errorResponse, fakeMe, stubApi } from "@/test/api";
import { routerPush, routerReplace, setLocation } from "@/test/navigation";

import { AppShell } from "./AppShell";

vi.mock("next/navigation", async () => (await import("@/test/navigation")).navigationMock());

describe("AppShell", () => {
  beforeEach(() => {
    setLocation("/team");
    routerPush.mockClear();
    routerReplace.mockClear();
  });

  it("shows the navigation and the page for a signed-in owner", async () => {
    stubApi({ "GET /api/v1/me": fakeMe() });

    render(
      <AppShell>
        <p>Page content</p>
      </AppShell>,
    );

    expect(await screen.findByText("Page content")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Team" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Consultants" })).toBeInTheDocument();
    expect(screen.getByLabelText("Organisation")).toHaveDisplayValue("Acme");
  });

  it("marks the page the visitor is on in the navigation", async () => {
    stubApi({ "GET /api/v1/me": fakeMe() });

    render(
      <AppShell>
        <p>Page content</p>
      </AppShell>,
    );

    expect(await screen.findByRole("link", { name: "Team" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "Account" })).not.toHaveAttribute("aria-current");
  });

  it("hides the manage links from a plain member", async () => {
    stubApi({
      "GET /api/v1/me": fakeMe({
        memberships: [
          {
            organisation_id: "22222222-2222-2222-2222-222222222222",
            organisation_name: "Acme",
            organisation_status: "active",
            role: "member",
          },
        ],
      }),
    });

    render(
      <AppShell>
        <p>Page content</p>
      </AppShell>,
    );

    expect(await screen.findByRole("link", { name: "Team" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Consultants" })).not.toBeInTheDocument();
  });

  it("sends a signed-out visitor to sign in, remembering where they were", async () => {
    setLocation("/team?x=1");
    stubApi({ "GET /api/v1/me": errorResponse("not_authenticated", "Please sign in.", 401) });

    render(
      <AppShell>
        <p>Page content</p>
      </AppShell>,
    );

    await vi.waitFor(() =>
      expect(routerReplace).toHaveBeenCalledWith("/sign-in?next=%2Fteam%3Fx%3D1"),
    );
    expect(screen.queryByText("Page content")).not.toBeInTheDocument();
  });

  it("sends the visitor to sign in when a later call answers 401", async () => {
    setLocation("/team?x=1");
    stubApi({
      "GET /api/v1/me": fakeMe(),
      "GET /api/v1/organisation": errorResponse("not_authenticated", "Please sign in.", 401),
    });
    const user = userEvent.setup();

    render(
      <AppShell>
        <button onClick={() => void getJson("/organisation").catch(() => undefined)}>
          Load the organisation
        </button>
      </AppShell>,
    );
    await user.click(await screen.findByRole("button", { name: "Load the organisation" }));

    await vi.waitFor(() =>
      expect(routerReplace).toHaveBeenCalledWith("/sign-in?next=%2Fteam%3Fx%3D1"),
    );
  });

  it("switches the active organisation from the switcher", async () => {
    const me = fakeMe({
      memberships: [
        ...fakeMe().memberships,
        {
          organisation_id: "99999999-9999-9999-9999-999999999999",
          organisation_name: "Beta Ltd",
          organisation_status: "active",
          role: "member",
        },
      ],
    });
    const switched = { ...me, active_organisation_id: "99999999-9999-9999-9999-999999999999" };
    const calls = stubApi({
      "GET /api/v1/me": me,
      "POST /api/v1/me/active-organisation": switched,
    });
    const user = userEvent.setup();

    render(
      <AppShell>
        <p>Page content</p>
      </AppShell>,
    );
    await user.selectOptions(
      await screen.findByLabelText("Organisation"),
      "99999999-9999-9999-9999-999999999999",
    );

    expect(calls.at(-1)).toMatchObject({
      method: "POST",
      path: "/api/v1/me/active-organisation",
      body: { organisation_id: "99999999-9999-9999-9999-999999999999" },
    });
    expect(await screen.findByLabelText("Organisation")).toHaveDisplayValue("Beta Ltd");
  });

  it("signs out and goes to the sign-in page", async () => {
    const calls = stubApi({
      "GET /api/v1/me": fakeMe(),
      "POST /api/v1/auth/sign-out": { message: "You are signed out." },
    });
    const user = userEvent.setup();

    render(
      <AppShell>
        <p>Page content</p>
      </AppShell>,
    );
    await user.click(await screen.findByRole("button", { name: "Sign out" }));

    expect(calls.at(-1)).toMatchObject({ method: "POST", path: "/api/v1/auth/sign-out" });
    expect(routerPush).toHaveBeenCalledWith("/sign-in");
  });
});
