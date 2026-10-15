"use client";

import { useId } from "react";
import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";

const INPUT =
  "block w-full rounded-md border px-3 py-2 text-sm text-neutral-900 " +
  "focus:outline-2 focus:-outline-offset-1 disabled:bg-neutral-100 disabled:text-neutral-500";

function inputClass(error: boolean): string {
  return `${INPUT} ${
    error
      ? "border-red-400 focus:outline-red-700"
      : "border-neutral-300 focus:outline-neutral-900"
  }`;
}

interface FieldChrome {
  label: string;
  /** Keep the label for screen readers only, e.g. for a control inside a table row. */
  labelHidden?: boolean;
  hint?: string;
  error?: string;
}

function Chrome({
  id,
  label,
  labelHidden,
  hint,
  error,
  children,
}: FieldChrome & { id: string; children: ReactNode }) {
  return (
    <div>
      <label
        htmlFor={id}
        className={labelHidden ? "sr-only" : "block text-sm font-medium text-neutral-900"}
      >
        {label}
      </label>
      <div className="mt-1">{children}</div>
      {hint && !error && (
        <p id={`${id}-hint`} className="mt-1 text-xs text-neutral-500">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="mt-1 text-xs text-red-700">
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
        className={inputClass(Boolean(error))}
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
        className={`${inputClass(Boolean(error))} bg-white`}
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
    <div className="flex items-start gap-2">
      <input
        id={fieldId}
        type="checkbox"
        className="mt-0.5 h-4 w-4 rounded border-neutral-300 accent-neutral-900"
        {...rest}
      />
      <label htmlFor={fieldId} className="text-sm text-neutral-700">
        {label}
      </label>
    </div>
  );
}
