
"use client";

import { useId, useState } from "react";
import type { InputHTMLAttributes } from "react";

type AuthInputProps = Omit<
    InputHTMLAttributes<HTMLInputElement>,
    "type"
> & {
    label: string;
    type: "email" | "password" | "text";
    error?: string;
    hint?: string;
};

function FieldIcon({
    type,
}: {
    type: "email" | "password" | "text";
}) {
    const common = {
        width: 19,
        height: 19,
        viewBox: "0 0 24 24",
        fill: "none",
        stroke: "currentColor",
        strokeWidth: 1.7,
        strokeLinecap: "round" as const,
        strokeLinejoin: "round" as const,
    };

    if (type === "text") {
        return (
            <svg {...common} aria-hidden="true">
                <circle cx="12" cy="8" r="4" />
                <path d="M4 21v-2a8 8 0 0 1 16 0v2" />
            </svg>
        );
    }

    if (type === "password") {
        return (
            <svg {...common} aria-hidden="true">
                <rect x="4" y="11" width="16" height="10" rx="2" />
                <path d="M8 11V7a4 4 0 0 1 8 0v4" />
            </svg>
        );
    }

    return (
        <svg {...common} aria-hidden="true">
            <rect x="3" y="5" width="18" height="14" rx="2" />
            <path d="m3 7 9 6 9-6" />
        </svg>
    );
}

function VisibilityIcon({
    visible,
}: {
    visible: boolean;
}) {
    return (
        <svg
            width="19"
            height="19"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.7"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
        >
            {visible ? (
                <>
                    <path d="M3 3l18 18" />
                    <path d="M10.6 10.6a2 2 0 0 0 2.8 2.8" />
                    <path d="M9.9 5.2A11 11 0 0 1 12 5c5 0 9 4 10 7a13 13 0 0 1-3 4.2" />
                    <path d="M6.1 6.1C3.9 7.5 2.5 9.5 2 12c1 3 5 7 10 7 1.7 0 3.3-.5 4.6-1.3" />
                </>
            ) : (
                <>
                    <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z" />
                    <circle cx="12" cy="12" r="3" />
                </>
            )}
        </svg>
    );
}

export function AuthInput({
    label,
    type,
    error,
    hint,
    id,
    className = "",
    ...props
}: AuthInputProps) {
    const generatedId = useId();
    const inputId = id ?? generatedId;

    const [visible, setVisible] = useState(false);
    const isPassword = type === "password";

    const actualType =
        isPassword && visible ? "text" : type;

    const describedBy = [
        hint && !error ? `${inputId}-hint` : null,
        error ? `${inputId}-error` : null,
    ]
        .filter(Boolean)
        .join(" ") || undefined;

    return (
        <div className="w-full">
            <label
                htmlFor={inputId}
                className="mb-2 block text-sm font-medium text-[#26394B]"
            >
                {label}
            </label>

            <div className="relative">
                <div
                    aria-hidden="true"
                    className="pointer-events-none absolute inset-y-0 left-4 flex items-center text-[#8193A8]"
                >
                    <FieldIcon type={type} />
                </div>

                <input
                    {...props}
                    id={inputId}
                    type={actualType}
                    aria-invalid={Boolean(error)}
                    aria-describedby={describedBy}
                    className={[
                        "h-12 w-full rounded-xl border bg-[#F3F6FA]",
                        "pl-12 text-sm text-[#10243B]",
                        "placeholder:text-[#8796AA]",
                        "outline-none transition-[border-color,box-shadow,background-color] duration-200",
                        "hover:border-[#AEBCCB]",
                        "focus:border-[#304E73] focus:bg-white",
                        "focus:ring-4 focus:ring-[#10243B]/10",
                        "disabled:cursor-not-allowed disabled:bg-slate-100",
                        "disabled:text-slate-500",
                        isPassword ? "pr-12" : "pr-4",
                        error
                            ? "border-red-400 focus:border-red-500 focus:ring-red-100"
                            : "border-[#D6DFE9]",
                        className,
                    ].join(" ")}
                />

                {isPassword && (
                    <button
                        type="button"
                        onClick={() => setVisible((previous) => !previous)}
                        aria-label={
                            visible ? "Hide password" : "Show password"
                        }
                        aria-pressed={visible}
                        disabled={props.disabled}
                        className="absolute inset-y-0 right-2 flex w-10 items-center justify-center rounded-lg text-[#8193A8] transition-colors hover:text-[#10243B] focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[#304E73] disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        <VisibilityIcon visible={visible} />
                    </button>
                )}
            </div>

            {hint && !error && (
                <p
                    id={`${inputId}-hint`}
                    className="mt-1.5 text-xs text-[#64748B]"
                >
                    {hint}
                </p>
            )}

            {error && (
                <p
                    id={`${inputId}-error`}
                    role="alert"
                    className="mt-1.5 text-xs text-red-600"
                >
                    {error}
                </p>
            )}
        </div>
    );
}
