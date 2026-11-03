// Money from the API is a decimal string in major units ("50000.00") with an ISO 4217
// code. Formatting uses the runtime's own currency data, like lib/currencies.ts.

export function currencyDecimals(currency: string): number {
  try {
    return (
      new Intl.NumberFormat("en", { style: "currency", currency }).resolvedOptions()
        .maximumFractionDigits ?? 2
    );
  } catch {
    return 2;
  }
}

/** "$50,000.00", "¥1,235". Falls back to "50000.00 USD" for a code Intl does not know. */
export function formatMoney(amount: string, currency: string): string {
  const value = Number(amount);
  if (!Number.isFinite(value)) return `${amount} ${currency}`;
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(value);
  } catch {
    return `${amount} ${currency}`;
  }
}

/** The amount typed in a form is a valid major-unit amount for the currency: digits, one
 * optional decimal point, and no more decimals than the currency has. */
export function moneyError(input: string, currency: string): string | undefined {
  const text = input.trim();
  if (!text) return undefined;
  if (!/^\d+(\.\d+)?$/.test(text)) return "Enter a number, like 50000 or 50000.00.";
  const decimals = text.split(".")[1]?.length ?? 0;
  const allowed = currencyDecimals(currency);
  if (decimals > allowed) {
    return allowed === 0
      ? `${currency} amounts have no decimals.`
      : `${currency} amounts have at most ${allowed} decimal places.`;
  }
  return undefined;
}
