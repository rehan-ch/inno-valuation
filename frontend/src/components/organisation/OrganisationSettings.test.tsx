import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { RecordedCall } from "@/test/api";
import { errorResponse, fakeMe, fakeOrganisation, stubApi } from "@/test/api";
import { renderWithMe } from "@/test/me";

import { OrganisationSettings } from "./OrganisationSettings";

vi.mock("next/navigation", async () => (await import("@/test/navigation")).navigationMock());

describe("OrganisationSettings", () => {
  it("prefills the profile and saves the changes", async () => {
    const org = fakeOrganisation({ industry: "Retail" });
    const calls = stubApi({
      "GET /api/v1/organisation": org,
      "PATCH /api/v1/organisation": (call: RecordedCall) => ({ ...org, ...(call.body as object) }),
    });
    const user = userEvent.setup();

    const { refresh } = renderWithMe(<OrganisationSettings />, fakeMe());

    const name = await screen.findByLabelText("Name");
    expect(name).toHaveDisplayValue("Acme");
    expect(screen.getByLabelText("Industry")).toHaveDisplayValue("Retail");
    await user.clear(name);
    await user.type(name, "Acme Ltd");
    await user.type(screen.getByLabelText("Country"), "us");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Saved.");
    expect(calls.at(-1)).toMatchObject({
      method: "PATCH",
      path: "/api/v1/organisation",
      body: { name: "Acme Ltd", industry: "Retail", country: "US", currency: "USD" },
    });
    expect(refresh).toHaveBeenCalled(); // the switcher shows the new name
  });

  it("shows the backend message when saving fails", async () => {
    stubApi({
      "GET /api/v1/organisation": fakeOrganisation(),
      "PATCH /api/v1/organisation": errorResponse(
        "validation_error",
        "The request is not valid.",
        422,
      ),
    });
    const user = userEvent.setup();

    renderWithMe(<OrganisationSettings />, fakeMe());
    await user.click(await screen.findByRole("button", { name: "Save changes" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("The request is not valid.");
  });

  it("tells a plain member the profile is for owners and admins", async () => {
    stubApi({ "GET /api/v1/organisation": fakeOrganisation({ role: "member" }) });

    renderWithMe(<OrganisationSettings />, fakeMe());

    expect(
      await screen.findByText("Only an owner or admin can edit the organisation profile."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save changes" })).not.toBeInTheDocument();
  });

  it("keeps an archived organisation view-only", async () => {
    stubApi({ "GET /api/v1/organisation": fakeOrganisation({ status: "archived" }) });

    renderWithMe(<OrganisationSettings />, fakeMe());

    expect(
      await screen.findByText("This organisation is archived, so its profile is view-only."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save changes" })).not.toBeInTheDocument();
  });
});
