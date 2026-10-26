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

  it("shows and saves the new organisation after a switch in the header", async () => {
    const BETA = "99999999-9999-9999-9999-999999999999";
    const acme = fakeOrganisation({ industry: "Retail" });
    const beta = fakeOrganisation({ id: BETA, name: "Beta Ltd", industry: "Finance", currency: "EUR" });
    let current = acme;
    let releaseLoad: () => void = () => {};
    const calls = stubApi({
      "GET /api/v1/organisation": () =>
        current === acme
          ? acme
          : new Promise((resolve) => {
              releaseLoad = () => resolve(beta);
            }),
      "PATCH /api/v1/organisation": (call: RecordedCall) => ({ ...current, ...(call.body as object) }),
    });
    const me = fakeMe({
      memberships: [
        ...fakeMe().memberships,
        {
          organisation_id: BETA,
          organisation_name: "Beta Ltd",
          organisation_status: "active",
          role: "owner",
        },
      ],
    });
    const user = userEvent.setup();

    const { setMe } = renderWithMe(<OrganisationSettings />, me);
    expect(await screen.findByLabelText("Name")).toHaveDisplayValue("Acme");

    current = beta;
    setMe({ ...me, active_organisation_id: BETA });

    // While the new organisation loads, the old form is gone: nothing to save against it.
    expect(await screen.findByText("Loading the organisation...")).toBeInTheDocument();
    expect(screen.queryByLabelText("Name")).not.toBeInTheDocument();
    releaseLoad();
    expect(await screen.findByLabelText("Name")).toHaveDisplayValue("Beta Ltd");
    expect(screen.getByLabelText("Industry")).toHaveDisplayValue("Finance");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Saved.");
    expect(calls.at(-1)).toMatchObject({
      method: "PATCH",
      body: { name: "Beta Ltd", industry: "Finance", currency: "EUR" },
    });
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
