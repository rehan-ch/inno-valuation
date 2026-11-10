import { describe, expect, it } from "vitest";

import { csvCell, toCsv } from "./csv";

describe("csvCell", () => {
  it("leaves plain text and numbers alone", () => {
    expect(csvCell("Customer Journey")).toBe("Customer Journey");
    expect(csvCell("70.0 / 100.0")).toBe("70.0 / 100.0");
  });

  it("quotes commas, quotes and line breaks", () => {
    expect(csvCell('Fast, "smart" delivery')).toBe('"Fast, ""smart"" delivery"');
    expect(csvCell("two\nlines")).toBe('"two\nlines"');
  });

  it("writes a would-be formula as text", () => {
    expect(csvCell("=SUM(A1:A9)")).toBe("'=SUM(A1:A9)");
    expect(csvCell("+1")).toBe("'+1");
    expect(csvCell("-7")).toBe("'-7");
    expect(csvCell("@cmd")).toBe("'@cmd");
    expect(csvCell('=HYPERLINK("x","y")')).toBe('"\'=HYPERLINK(""x"",""y"")"');
  });
});

describe("toCsv", () => {
  it("joins rows and cells", () => {
    expect(toCsv([["", "A, B"], ["IQ", "70.0"]])).toBe(',"A, B"\nIQ,70.0');
  });
});
