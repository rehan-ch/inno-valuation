import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { fakeGrant, fakeMe, fakeOrganisation, stubApi } from "@/test/api";
import { renderWithMe } from "@/test/me";

import { ConsultantsPage } from "./ConsultantsPage";

describe("ConsultantsPage", () => {
  it("grants access until the end of the chosen day in UTC", async () => {
    const calls = stubApi({
      "GET /api/v1/organisation": fakeOrganisation(),
      "GET /api/v1/organisation/consultants": [],
      "POST /api/v1/organisation/consultants": fakeGrant(),
    });
    const user = userEvent.setup();

    renderWithMe(<ConsultantsPage />, fakeMe());
    await user.type(await screen.findByLabelText("Consultant's email"), "amy@example.com");
    await user.type(screen.getByLabelText("Access ends on"), "2026-12-31");
    await user.click(screen.getByRole("button", { name: "Give access" }));

    expect(calls.at(-1)).toMatchObject({
      method: "POST",
      path: "/api/v1/organisation/consultants",
      body: { email: "amy@example.com", expires_at: "2026-12-31T23:59:59Z" },
    });
    expect(await screen.findByRole("status")).toHaveTextContent(
      "We sent an email to amy@example.com.",
    );
    expect(screen.getByText("Waiting for the consultant")).toBeInTheDocument();
  });

  it("revokes access after an inline confirmation", async () => {
    const grant = fakeGrant({ status: "active", accepted_at: "2026-10-15T10:00:00Z" });
    const calls = stubApi({
      "GET /api/v1/organisation": fakeOrganisation(),
      "GET /api/v1/organisation/consultants": [grant],
      "DELETE /api/v1/organisation/consultants/55555555-5555-5555-5555-555555555555": {
        ...grant,
        status: "revoked",
        revoked_at: "2026-10-15T12:00:00Z",
      },
    });
    const user = userEvent.setup();

    renderWithMe(<ConsultantsPage />, fakeMe());
    await user.click(await screen.findByRole("button", { name: "Revoke" }));
    await user.click(screen.getByRole("button", { name: "End access now?" }));

    expect(calls.at(-1)).toMatchObject({
      method: "DELETE",
      path: "/api/v1/organisation/consultants/55555555-5555-5555-5555-555555555555",
    });
    expect(await screen.findByText("Revoked")).toBeInTheDocument();
  });

  it("changes the end date of a grant", async () => {
    const grant = fakeGrant({ status: "active" });
    const calls = stubApi({
      "GET /api/v1/organisation": fakeOrganisation(),
      "GET /api/v1/organisation/consultants": [grant],
      "PATCH /api/v1/organisation/consultants/55555555-5555-5555-5555-555555555555": {
        ...grant,
        expires_at: "2027-03-31T23:59:59Z",
      },
    });
    const user = userEvent.setup();

    renderWithMe(<ConsultantsPage />, fakeMe());
    await user.click(await screen.findByRole("button", { name: "Change end date" }));
    await user.type(screen.getByLabelText("New end date for amy@example.com"), "2027-03-31");
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(calls.at(-1)).toMatchObject({
      method: "PATCH",
      body: { expires_at: "2027-03-31T23:59:59Z" },
    });
  });

  it("tells a plain member this page is for owners and admins", async () => {
    stubApi({
      "GET /api/v1/organisation": fakeOrganisation({ role: "member" }),
    });

    renderWithMe(<ConsultantsPage />, fakeMe());

    expect(
      await screen.findByText("Only an owner or admin of an active organisation can manage this."),
    ).toBeInTheDocument();
  });
});
