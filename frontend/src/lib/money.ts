// Money from the API is a decimal string in major units ("50000.00") with an ISO 4217
// code. The server quantises every amount to the currency's minor units, so the string
// already carries the right number of decimals and is shown as sent.

// ISO 4217 minor units, the same table as the server's core/currencies.py (the runtime's
// own currency data disagrees with it for several currencies, e.g. IQD, LBP and RSD).
const ZERO_DECIMALS = new Set([
  "BIF", "CLP", "DJF", "GNF", "ISK", "JPY", "KMF", "KRW", "PYG", "RWF", "UGX", "UYI",
  "VND", "VUV", "XAF", "XOF", "XPF",
]);
const THREE_DECIMALS = new Set(["BHD", "IQD", "JOD", "KWD", "LYD", "OMR", "TND"]);
const FOUR_DECIMALS = new Set(["CLF", "UYW"]);

export function currencyDecimals(currency: string): number {
  if (ZERO_DECIMALS.has(currency)) return 0;
  if (THREE_DECIMALS.has(currency)) return 3;
  if (FOUR_DECIMALS.has(currency)) return 4;
  return 2;
}

/** "$50,000.00", "¥1,235", "¥714.29" for a per-point figure the server gave to 2 decimals.
 * Falls back to "50000.00 USD" for a code Intl does not know. */
export function formatMoney(amount: string, currency: string): string {
  const value = Number(amount);
  if (!Number.isFinite(value)) return `${amount} ${currency}`;
  const decimals = amount.split(".")[1]?.length ?? 0;
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency,
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }).format(value);
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
