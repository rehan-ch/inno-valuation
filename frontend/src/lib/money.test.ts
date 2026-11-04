import { describe, expect, it } from "vitest";

import { currencyDecimals, formatMoney, moneyError } from "./money";

describe("currencyDecimals", () => {
  it("follows the ISO 4217 table the server uses, not the runtime's locale data", () => {
    expect(currencyDecimals("USD")).toBe(2);
    expect(currencyDecimals("JPY")).toBe(0);
    expect(currencyDecimals("IQD")).toBe(3);
    expect(currencyDecimals("LBP")).toBe(2);
    expect(currencyDecimals("CLF")).toBe(4);
  });
});

describe("moneyError", () => {
  it("accepts what the server accepts", () => {
    expect(moneyError("100.500", "IQD")).toBeUndefined();
    expect(moneyError("1500.50", "LBP")).toBeUndefined();
    expect(moneyError("1500.5", "JPY")).toBe("JPY amounts have no decimals.");
    expect(moneyError("1.234", "USD")).toBe("USD amounts have at most 2 decimal places.");
  });
});

describe("formatMoney", () => {
  it("shows every decimal the server sent", () => {
    // A per-point figure is always given to 2 decimals, even for a 0-decimal currency.
    expect(formatMoney("714.29", "JPY")).toMatch(/714\.29/);
    expect(formatMoney("100.500", "IQD")).toMatch(/100\.500/);
    expect(formatMoney("50000", "JPY")).toMatch(/50,000$/);
    expect(formatMoney("50000.00", "USD")).toMatch(/50,000\.00/);
  });

  it("falls back to the plain amount for an unknown code", () => {
    expect(formatMoney("12.00", "not-a-code")).toBe("12.00 not-a-code");
    expect(formatMoney("abc", "USD")).toBe("abc USD");
  });
});
