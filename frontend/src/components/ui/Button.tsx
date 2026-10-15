import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "danger";

const BASE =
  "inline-flex items-center justify-center rounded-md px-3 py-2 text-sm font-medium " +
  "focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-neutral-900 text-white hover:bg-neutral-700 focus-visible:outline-neutral-900 " +
    "disabled:bg-neutral-400",
  secondary:
    "border border-neutral-300 bg-white text-neutral-900 hover:bg-neutral-50 " +
    "focus-visible:outline-neutral-900 disabled:text-neutral-400",
  danger:
    "border border-red-300 bg-white text-red-700 hover:bg-red-50 " +
    "focus-visible:outline-red-700 disabled:text-red-300",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  /** Disables the button while its action runs. */
  busy?: boolean;
}

export function Button({
  variant = "primary",
  busy = false,
  disabled,
  type = "button",
  className,
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      className={`${BASE} ${VARIANTS[variant]}${className ? ` ${className}` : ""}`}
      {...rest}
    >
      {children}
    </button>
  );
}
