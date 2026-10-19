import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Table, Td, Th } from "./Table";

describe("Table", () => {
  it("renders a described table with header and body rows", () => {
    render(
      <Table
        caption="Ideas with their scores"
        head={
          <>
            <Th>Idea</Th>
            <Th>Score</Th>
          </>
        }
      >
        <tr>
          <Td>Faster onboarding</Td>
          <Td>70.0</Td>
        </tr>
      </Table>,
    );

    expect(screen.getByRole("table", { name: "Ideas with their scores" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Idea" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Faster onboarding" })).toBeInTheDocument();
  });
});
