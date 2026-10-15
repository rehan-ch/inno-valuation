import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { fakeAccess, fakeMe, stubApi } from "@/test/api";
import { renderWithMe } from "@/test/me";

import { MyAccessPage } from "./MyAccessPage";

describe("MyAccessPage", () => {
  it("accepts waiting access and refreshes the account for the switcher", async () => {
    const calls = stubApi({
      "GET /api/v1/me/consultant-access": [fakeAccess()],
      "POST /api/v1/me/consultant-access/55555555-5555-5555-5555-555555555555/accept": fakeAccess({
        status: "active",
      }),
    });
    const user = userEvent.setup();

    const { refresh } = renderWithMe(<MyAccessPage />, fakeMe());
    await user.click(await screen.findByRole("button", { name: "Accept" }));

    expect(calls.at(-1)).toMatchObject({
      method: "POST",
      path: "/api/v1/me/consultant-access/55555555-5555-5555-5555-555555555555/accept",
    });
    expect(await screen.findByText("Active")).toBeInTheDocument();
    expect(refresh).toHaveBeenCalled();
  });

  it("shows an empty state when no access is given", async () => {
    stubApi({ "GET /api/v1/me/consultant-access": [] });

    renderWithMe(<MyAccessPage />, fakeMe());

    expect(
      await screen.findByText("No organisation has given you access yet.", { exact: false }),
    ).toBeInTheDocument();
  });
});
