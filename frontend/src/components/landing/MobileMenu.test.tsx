import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { MobileMenu } from "./MobileMenu";

describe("MobileMenu", () => {
  it("closes once one of its links is used", async () => {
    const user = userEvent.setup();
    const { container } = render(
      <MobileMenu>
        <summary>Menu</summary>
        <a href="#features">Features</a>
      </MobileMenu>,
    );
    const details = container.querySelector("details")!;

    await user.click(screen.getByText("Menu"));
    expect(details).toHaveAttribute("open");
    await user.click(screen.getByRole("link", { name: "Features" }));
    expect(details).not.toHaveAttribute("open");
  });
});
