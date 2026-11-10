import { readFileSync } from "node:fs";
import { join } from "node:path";

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { fakeCompass, fakeQuestionSet } from "@/test/api";

import { Compass, gapWords } from "./Compass";

const hrefFor = (key: string) => `/dimensions/${key}`;

function renderCompass(scale: "readiness" | "iq", change?: (c: ReturnType<typeof fakeCompass>) => void) {
  const compass = fakeCompass(scale);
  change?.(compass);
  render(
    <Compass
      title={scale === "readiness" ? "Readiness compass" : "Idea compass"}
      compass={compass}
      headline={{ value: scale === "readiness" ? "190" : "70.0", maximum: scale === "readiness" ? "300" : "100", label: "Building Blocks" }}
      hrefFor={hrefFor}
    />,
  );
  return compass;
}

describe("Compass", () => {
  it("draws one segment per dimension, in the order it was sent, each a link", () => {
    const compass = renderCompass("readiness");
    const chart = screen.getByRole("group", {
      name: "Readiness compass: 6 dimensions in 3 categories",
    });
    const segments = within(chart).getAllByRole("link");
    expect(segments.map((s) => s.getAttribute("href"))).toEqual(
      compass.segments.map((s) => `/dimensions/${s.key}`),
    );
    expect(segments[0]).toHaveAccessibleName("Customer Journey: 20 out of 25");
    // The headline figure sits in the middle until a segment is chosen.
    expect(within(chart).getByText("190")).toBeInTheDocument();
    expect(within(chart).getByText("out of 300")).toBeInTheDocument();
  });

  it("has a table of the same numbers, grouped by category with category scores", () => {
    renderCompass("readiness");
    const table = screen.getByRole("table", { name: /every dimension's score/ });
    const groups = within(table).getAllByRole("rowgroup").slice(1); // after the head
    expect(groups).toHaveLength(3);
    expect(within(groups[0]!).getByRole("rowheader", { name: "Customer-Facing Innovation" })).toBeInTheDocument();
    expect(within(groups[0]!).getByText("40 / 50")).toBeInTheDocument();
    const row = within(table).getByRole("row", { name: /Data Intelligence/ });
    expect(row).toHaveTextContent("12 / 25");
    expect(within(row).getByRole("link", { name: /Data Intelligence/ })).toHaveAttribute(
      "href",
      "/dimensions/data_intelligence",
    );
  });

  it("shows no level for readiness, because the method has none per dimension", () => {
    renderCompass("readiness");
    expect(screen.queryByRole("list", { name: "Levels" })).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Level" })).not.toBeInTheDocument();
    expect(screen.getByText("Each segment fills as far as its score out of 25.")).toBeInTheDocument();
  });

  it("colours idea segments by the level the server sent, with a legend", () => {
    renderCompass("iq");
    const legend = screen.getByRole("list", { name: "Levels" });
    expect(within(legend).getAllByRole("listitem").map((li) => li.textContent)).toEqual([
      "Continuous Improvement 1 to 3",
      "Innovation 4 to 6",
      "Invention 7 to 10",
    ]);
    const chart = screen.getByRole("group", { name: /Idea compass/ });
    const fill = (name: RegExp) =>
      within(chart).getByRole("link", { name }).querySelectorAll("path")[1]?.getAttribute("fill");
    // 8 is the highest level, 3 the lowest, 6 the middle: three steps of one ramp.
    expect(fill(/Customer Journey: 8 out of 10, Invention/)).toBe("var(--color-ramp-3)");
    expect(fill(/Organizational Agility: 3 out of 10, Continuous Improvement/)).toBe("var(--color-ramp-1)");
    expect(fill(/Operational Efficiency: 6 out of 10, Innovation/)).toBe("var(--color-ramp-2)");
    const row = screen.getByRole("row", { name: /Organizational Agility/ });
    expect(row).toHaveTextContent("Continuous Improvement");
  });

  it("shows targets and gaps only when a target is set, in the server's words", () => {
    renderCompass("iq", (compass) => {
      Object.assign(compass.segments[3]!, { target: 8, gap: 5, priority_rank: 1 });
      Object.assign(compass.segments[0]!, { target: 8, gap: 0 });
      Object.assign(compass.segments[4]!, { target: 6, gap: -2 });
    });
    expect(screen.getByRole("columnheader", { name: "Target" })).toBeInTheDocument();
    expect(screen.getByRole("row", { name: /Organizational Agility/ })).toHaveTextContent(
      /priority 1.*3 \/ 10.*8.*5 below target/,
    );
    expect(screen.getByRole("row", { name: /Customer Journey/ })).toHaveTextContent("on target");
    expect(screen.getByRole("row", { name: /Data Intelligence/ })).toHaveTextContent("2 above target");
    expect(
      screen.getByRole("link", {
        name: "Organizational Agility: 3 out of 10, Continuous Improvement, target 8, 5 below target",
      }),
    ).toBeInTheDocument();
  });

  it("puts the focused segment's score in the middle, so the keyboard reaches every one", async () => {
    renderCompass("iq");
    const user = userEvent.setup();
    const chart = screen.getByRole("group", { name: /Idea compass/ });
    await user.tab();
    expect(within(chart).getAllByRole("link")[0]).toHaveFocus();
    expect(within(chart).getByText("1. Customer Journey")).toBeInTheDocument();
    await user.tab();
    expect(within(chart).getByText("2. Brand Magnetism")).toBeInTheDocument();
    expect(within(chart).queryByText("1. Customer Journey")).not.toBeInTheDocument();
  });

  it("words a gap by its sign", () => {
    expect(gapWords(3)).toBe("3 below target");
    expect(gapWords(0)).toBe("on target");
    expect(gapWords(-2)).toBe("2 above target");
  });

  it("holds no dimension, category, level or formula of its own", () => {
    // Everything the compass draws comes from the payload: the source must not name a
    // dimension, a category or a level, nor carry a scale maximum.
    const source = readFileSync(join(__dirname, "Compass.tsx"), "utf8");
    const set = fakeQuestionSet();
    const words = [
      ...set.dimensions.flatMap((d) => [d.key, d.name]),
      ...set.categories.flatMap((c) => [c.key, c.name]),
      "Customer Journey",
      "customer_journey",
      "Financial Imperative",
      "Continuous Improvement",
      "Invention",
      "Building Blocks",
      "/ 120",
      "* 100",
      "/ 300",
      "/ 25",
    ];
    for (const word of words) {
      expect(source, `Compass.tsx mentions ${word}`).not.toContain(word);
    }
  });
});
