import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Button } from "./Button";
import { EmptyState } from "./EmptyState";

describe("EmptyState", () => {
  it("shows the title, the explanation and the action", () => {
    render(
      <EmptyState title="No ideas yet." action={<Button>Add an idea</Button>}>
        Add your first idea to see its score here.
      </EmptyState>,
    );

    expect(screen.getByText("No ideas yet.")).toBeInTheDocument();
    expect(screen.getByText("Add your first idea to see its score here.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add an idea" })).toBeInTheDocument();
  });
});
