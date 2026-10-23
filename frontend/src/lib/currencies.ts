// Currencies for the organisation setting, from the runtime's own ISO 4217 data
// (Intl), so there is no list to maintain. Names are in English, like the rest of the app.

export interface Currency {
  code: string;
  name: string;
}

// Real ISO codes, but not money an organisation invests in: the IMF's accounting unit,
// the Sucre unit of account, and "no currency".
const NOT_INVESTABLE = new Set(["XDR", "XSU", "XXX"]);

const names = new Intl.DisplayNames(["en"], { type: "currency" });

export const CURRENCIES: readonly Currency[] = Intl.supportedValuesOf("currency")
  .filter((code) => !NOT_INVESTABLE.has(code))
  .map((code) => ({ code, name: names.of(code) ?? code }));

export function currencyLabel(code: string): string {
  const name = names.of(code);
  return name && name !== code ? `${code} · ${name}` : code;
}

/** Codes that start with the query come first, then names that contain it. */
export function filterCurrencies(query: string): readonly Currency[] {
  const q = query.trim().toLowerCase();
  if (!q) return CURRENCIES;
  const byCode = CURRENCIES.filter((c) => c.code.toLowerCase().startsWith(q));
  const byName = CURRENCIES.filter(
    (c) => !c.code.toLowerCase().startsWith(q) && c.name.toLowerCase().includes(q),
  );
  return [...byCode, ...byName];
}
