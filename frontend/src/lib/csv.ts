// CSV files made in the browser from numbers the API already sent.

const FORMULA_START = /^[=+\-@\t\r]/;

/** One CSV cell. Text that a spreadsheet would run as a formula (a title starting with
 * "=", for example) is written as plain text; quotes, commas and line breaks are escaped. */
export function csvCell(value: string): string {
  const text = FORMULA_START.test(value) ? `'${value}` : value;
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function toCsv(rows: string[][]): string {
  return rows.map((cells) => cells.map(csvCell).join(",")).join("\n");
}

export function downloadCsv(filename: string, rows: string[][]): void {
  const blob = new Blob([toCsv(rows)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
