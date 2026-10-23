import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { fakeMe, fakeOrganisation, stubApi } from "@/test/api";
import { renderWithMe } from "@/test/me";
import { routerPush } from "@/test/navigation";

import { NewOrganisationForm } from "./NewOrganisationForm";

vi.mock("next/navigation", async () => (await import("@/test/navigation")).navigationMock());

describe("NewOrganisationForm", () => {
  it("creates the organisation, refreshes the account and goes to the team page", async () => {
    routerPush.mockClear();
    const calls = stubApi({ "POST /api/v1/organisations": fakeOrganisation() });
    const user = userEvent.setup();

    const { refresh } = renderWithMe(
      <NewOrganisationForm />,
      fakeMe({ active_organisation_id: null, memberships: [] }),
    );
    await user.type(screen.getByLabelText("Name"), "Acme");
    await user.type(screen.getByLabelText("Country"), "us");
    await user.click(screen.getByRole("button", { name: "Create organisation" }));

    expect(calls.at(-1)).toMatchObject({
      method: "POST",
      path: "/api/v1/organisations",
      body: {
        name: "Acme",
        country: "US",
        currency: "USD",
        industry: null,
        website: null,
      },
    });
    expect(refresh).toHaveBeenCalled();
    expect(routerPush).toHaveBeenCalledWith("/dashboard");
  });
});
