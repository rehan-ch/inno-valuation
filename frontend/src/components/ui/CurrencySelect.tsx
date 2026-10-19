"use client";

import {
  Combobox,
  ComboboxButton,
  ComboboxInput,
  ComboboxOption,
  ComboboxOptions,
  Description,
  Field,
  Label,
} from "@headlessui/react";
import { useState } from "react";

import { currencyLabel, filterCurrencies } from "@/lib/currencies";

/** A searchable currency picker: type a code ("eur") or a name ("pound") to narrow the list.
 * Headless UI's Combobox supplies the keyboard and screen-reader behaviour. */
export function CurrencySelect({
  label = "Currency",
  value,
  onChange,
  hint,
}: {
  label?: string;
  value: string;
  onChange: (code: string) => void;
  hint?: string;
}) {
  const [query, setQuery] = useState("");
  const options = filterCurrencies(query);

  return (
    <Field>
      <Label className="block text-sm font-medium text-neutral-900">{label}</Label>
      <Combobox
        value={value}
        onChange={(code: string | null) => {
          if (code) onChange(code);
        }}
        onClose={() => setQuery("")}
      >
        <div className="relative mt-1">
          <ComboboxInput
            className="block w-full rounded-lg border border-neutral-300 bg-white py-2 pr-9 pl-3 text-sm text-neutral-900 focus:outline-2 focus:-outline-offset-1 focus:outline-accent"
            displayValue={(code: string) => (code ? currencyLabel(code) : "")}
            onChange={(event) => setQuery(event.target.value)}
            onFocus={(event) => event.target.select()}
            autoComplete="off"
          />
          <ComboboxButton
            aria-label={`Show all ${label.toLowerCase()} options`}
            className="absolute inset-y-0 right-0 flex items-center px-3 text-neutral-500 hover:text-neutral-900"
          >
            <span aria-hidden="true" className="text-xs">
              ▾
            </span>
          </ComboboxButton>
          <ComboboxOptions className="absolute z-20 mt-1 max-h-60 w-full overflow-auto rounded-lg border border-neutral-200 bg-white py-1 text-sm shadow-lg empty:invisible">
            {options.length === 0 ? (
              <p className="px-3 py-2 text-neutral-500">No currency matches “{query}”.</p>
            ) : (
              options.map((currency) => (
                <ComboboxOption
                  key={currency.code}
                  value={currency.code}
                  className="flex cursor-pointer items-center gap-3 px-3 py-2 text-neutral-900 data-focus:bg-neutral-100 data-selected:font-medium"
                >
                  <span className="w-10 shrink-0 font-medium text-primary">{currency.code}</span>
                  <span className="truncate">{currency.name}</span>
                </ComboboxOption>
              ))
            )}
          </ComboboxOptions>
        </div>
      </Combobox>
      {hint && <Description className="mt-1 text-xs text-neutral-500">{hint}</Description>}
    </Field>
  );
}
