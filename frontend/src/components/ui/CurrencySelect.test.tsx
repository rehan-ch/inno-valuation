import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { CURRENCIES, filterCurrencies } from "@/lib/currencies";

import { CurrencySelect } from "./CurrencySelect";

function Harness({ onChange }: { onChange: (code: string) => void }) {
  const [value, setValue] = useState("USD");
  return (
    <CurrencySelect
      value={value}
      onChange={(code) => {
        setValue(code);
        onChange(code);
      }}
    />
  );
}

describe("currency data", () => {
  it("comes from the runtime's ISO list, without non-investable codes", () => {
    const codes = CURRENCIES.map((c) => c.code);
    expect(codes).toEqual(expect.arrayContaining(["USD", "EUR", "GBP", "PKR", "AED"]));
    expect(codes).not.toContain("XXX");
    expect(codes).not.toContain("XDR");
    expect(CURRENCIES.find((c) => c.code === "GBP")?.name).toBe("British Pound");
  });

  it("ranks code matches before name matches", () => {
    const results = filterCurrencies("eu").map((c) => c.code);
    expect(results[0]).toBe("EUR");
  });
});

describe("CurrencySelect", () => {
  it("shows the current currency with its name", () => {
    render(<Harness onChange={() => {}} />);
    expect(screen.getByRole("combobox", { name: "Currency" })).toHaveValue("USD · US Dollar");
  });

  it("finds a currency by name and selects it", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<Harness onChange={onChange} />);

    const box = screen.getByRole("combobox", { name: "Currency" });
    await user.click(box);
    await user.keyboard("{Control>}a{/Control}");
    await user.keyboard("pound");
    await user.click(await screen.findByRole("option", { name: /British Pound/ }));

    expect(onChange).toHaveBeenCalledWith("GBP");
    expect(box).toHaveValue("GBP · British Pound");
  });

  it("finds a currency by code with the keyboard", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<Harness onChange={onChange} />);

    await user.click(screen.getByRole("combobox", { name: "Currency" }));
    await user.keyboard("{Control>}a{/Control}pkr");
    await user.keyboard("{ArrowDown}{Enter}");

    expect(onChange).toHaveBeenCalledWith("PKR");
  });

  it("says so when nothing matches", async () => {
    const user = userEvent.setup();
    render(<Harness onChange={() => {}} />);

    await user.click(screen.getByRole("combobox", { name: "Currency" }));
    await user.keyboard("{Control>}a{/Control}zzzz");

    expect(await screen.findByText("No currency matches “zzzz”.")).toBeInTheDocument();
  });
});
