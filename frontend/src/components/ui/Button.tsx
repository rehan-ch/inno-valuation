import type { ButtonHTMLAttributes } from "react";

export type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";
export type ButtonSize = "sm" | "md";

const BASE =
  "inline-flex shrink-0 items-center justify-center gap-2 rounded-md font-medium whitespace-nowrap " +
  "transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 " +
  "disabled:cursor-not-allowed";

const SIZES: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-[13px]",
  md: "h-9 px-3.5 text-sm",
};

const VARIANTS: Record<ButtonVariant, string> = {
  primary:
    "bg-primary text-white hover:bg-primary-strong focus-visible:outline-primary " +
    "disabled:bg-neutral-300",
  secondary:
    "border border-neutral-300 bg-white text-neutral-800 shadow-xs hover:bg-neutral-50 " +
    "focus-visible:outline-primary disabled:bg-neutral-50 disabled:text-neutral-400 disabled:shadow-none",
  danger:
    "border border-neutral-300 bg-white text-red-700 shadow-xs hover:border-red-300 hover:bg-red-50 " +
    "focus-visible:outline-red-700 disabled:text-red-300 disabled:shadow-none",
  ghost:
    "text-neutral-700 hover:bg-neutral-100 hover:text-neutral-900 focus-visible:outline-primary " +
    "disabled:text-neutral-400 disabled:hover:bg-transparent",
};

/** The classes of a button, for links that should look like one. */
export function buttonClass(
  variant: ButtonVariant = "primary",
  size: ButtonSize = "md",
  className?: string,
): string {
  return `${BASE} ${SIZES[size]} ${VARIANTS[variant]}${className ? ` ${className}` : ""}`;
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Disables the button while its action runs. */
  busy?: boolean;
}

export function Button({
  variant = "primary",
  size = "md",
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
      className={buttonClass(variant, size, className)}
      {...rest}
    >
      {children}
    </button>
  );
}
