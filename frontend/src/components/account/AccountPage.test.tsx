import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { errorResponse, fakeMe, stubApi } from "@/test/api";
import { renderWithMe } from "@/test/me";

import { AccountPage } from "./AccountPage";

describe("AccountPage", () => {
  it("saves a new name and updates the cached account", async () => {
    const renamed = fakeMe({ name: "Olive Renamed" });
    const calls = stubApi({ "PATCH /api/v1/me": renamed });
    const user = userEvent.setup();

    const { update } = renderWithMe(<AccountPage />, fakeMe());
    const name = screen.getByLabelText("Name");
    await user.clear(name);
    await user.type(name, "Olive Renamed");
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(calls.at(-1)).toMatchObject({ method: "PATCH", body: { name: "Olive Renamed" } });
    expect(update).toHaveBeenCalledWith(renamed);
    expect(await screen.findByRole("status")).toHaveTextContent("Your name is saved.");
  });

  it("changes the password and shows the backend message", async () => {
    const calls = stubApi({
      "POST /api/v1/me/password": { message: "Your password is changed." },
    });
    const user = userEvent.setup();

    renderWithMe(<AccountPage />, fakeMe());
    await user.type(screen.getByLabelText("Current password"), "old-password-1");
    await user.type(screen.getByLabelText("New password"), "new-password-1");
    await user.click(screen.getByRole("button", { name: "Change password" }));

    expect(calls.at(-1)).toMatchObject({
      body: { current_password: "old-password-1", new_password: "new-password-1" },
    });
    expect(await screen.findByRole("status")).toHaveTextContent("Your password is changed.");
  });

  it("shows the backend error when the current password is wrong", async () => {
    stubApi({
      "POST /api/v1/me/password": errorResponse(
        "invalid_password",
        "The current password is not correct.",
        400,
      ),
    });
    const user = userEvent.setup();

    renderWithMe(<AccountPage />, fakeMe());
    await user.type(screen.getByLabelText("Current password"), "wrong-password");
    await user.type(screen.getByLabelText("New password"), "new-password-1");
    await user.click(screen.getByRole("button", { name: "Change password" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The current password is not correct.",
    );
  });
});
