import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Drawer, Modal } from "./Modal";

describe("Modal", () => {
  it("shows its title and content while open", () => {
    render(
      <Modal open title="Change end date" onClose={() => {}}>
        <p>Pick a new date.</p>
      </Modal>,
    );

    expect(screen.getByRole("dialog", { name: "Change end date" })).toBeInTheDocument();
    expect(screen.getByText("Pick a new date.")).toBeInTheDocument();
  });

  it("closes from the close button", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <Modal open title="Change end date" onClose={onClose}>
        <p>Pick a new date.</p>
      </Modal>,
    );

    await user.click(screen.getByRole("button", { name: "Close" }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes when the browser cancels it, as on Escape", () => {
    const onClose = vi.fn();
    render(
      <Modal open title="Change end date" onClose={onClose}>
        <p>Pick a new date.</p>
      </Modal>,
    );

    fireEvent(screen.getByRole("dialog"), new Event("cancel", { cancelable: true }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

describe("Drawer", () => {
  it("behaves like a dialog with the same close control", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <Drawer open title="Filters" onClose={onClose}>
        <p>Filter content.</p>
      </Drawer>,
    );

    expect(screen.getByRole("dialog", { name: "Filters" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Close" }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
