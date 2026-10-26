"use client";

import { useId } from "react";
import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";

type Size = "sm" | "md";

const INPUT =
  "block w-full rounded-md border bg-white text-neutral-900 shadow-xs " +
  "placeholder:text-neutral-400 focus:outline-2 focus:-outline-offset-1 " +
  "disabled:bg-neutral-50 disabled:text-neutral-500 disabled:shadow-none";

const SIZES: Record<Size, string> = {
  sm: "h-8 px-2.5 text-[13px]",
  md: "h-9 px-3 text-sm",
};

function inputClass(error: boolean, size: Size): string {
  return `${INPUT} ${SIZES[size]} ${
    error ? "border-red-400 focus:outline-red-700" : "border-neutral-300 focus:outline-primary"
  }`;
}

interface FieldChrome {
  label: string;
  /** Keep the label for screen readers only, e.g. for a control inside a table row. */
  labelHidden?: boolean;
  hint?: string;
  error?: string;
  /** Compact controls for table rows and toolbars. */
  compact?: boolean;
}

function Chrome({
  id,
  label,
  labelHidden,
  hint,
  error,
  children,
}: Omit<FieldChrome, "compact"> & { id: string; children: ReactNode }) {
  return (
    <div>
      <label
        htmlFor={id}
        className={labelHidden ? "sr-only" : "block text-[13px] font-medium text-neutral-800"}
      >
        {label}
      </label>
      <div className={labelHidden ? undefined : "mt-1.5"}>{children}</div>
      {hint && !error && (
        <p id={`${id}-hint`} className="mt-1.5 text-xs text-neutral-500">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="mt-1.5 text-xs text-red-700">
          {error}
        </p>
      )}
    </div>
  );
}

function describedBy(id: string, hint?: string, error?: string): string | undefined {
  if (error) return `${id}-error`;
  if (hint) return `${id}-hint`;
  return undefined;
}

export function TextField({
  label,
  labelHidden,
  hint,
  error,
  compact = false,
  id,
  ...rest
}: FieldChrome & InputHTMLAttributes<HTMLInputElement>) {
  const generated = useId();
  const fieldId = id ?? generated;
  return (
    <Chrome id={fieldId} label={label} labelHidden={labelHidden} hint={hint} error={error}>
      <input
        id={fieldId}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(fieldId, hint, error)}
        className={inputClass(Boolean(error), compact ? "sm" : "md")}
        {...rest}
      />
    </Chrome>
  );
}

export function SelectField({
  label,
  labelHidden,
  hint,
  error,
  compact = false,
  id,
  children,
  ...rest
}: FieldChrome & SelectHTMLAttributes<HTMLSelectElement>) {
  const generated = useId();
  const fieldId = id ?? generated;
  return (
    <Chrome id={fieldId} label={label} labelHidden={labelHidden} hint={hint} error={error}>
      <select
        id={fieldId}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(fieldId, hint, error)}
        className={`${inputClass(Boolean(error), compact ? "sm" : "md")} pr-8`}
        {...rest}
      >
        {children}
      </select>
    </Chrome>
  );
}

export function CheckboxField({
  label,
  id,
  ...rest
}: { label: ReactNode } & InputHTMLAttributes<HTMLInputElement>) {
  const generated = useId();
  const fieldId = id ?? generated;
  return (
    <div className="flex items-start gap-2.5">
      <input
        id={fieldId}
        type="checkbox"
        className="mt-0.5 h-4 w-4 rounded border-neutral-300 accent-primary"
        {...rest}
      />
      <label htmlFor={fieldId} className="text-sm text-neutral-700">
        {label}
      </label>
    </div>
  );
}
