
"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { ComponentType, KeyboardEvent } from "react";
import {
    Check,
    ChevronDown,
    Crown,
    Eye,
    ShieldCheck,
    UserRound,
    UsersRound,
} from "lucide-react";

import type { MembershipRole } from "@/lib/api/types";
import { roleLabel } from "@/lib/roles";

type RoleIcon = ComponentType<{
    size?: number;
    strokeWidth?: number;
    className?: string;
}>;

const ROLE_DETAILS: Partial<
    Record<MembershipRole, { icon: RoleIcon; description: string }>
> = {
    owner: {
        icon: Crown,
        description: "Organisation ownership",
    },
    admin: {
        icon: ShieldCheck,
        description: "Organisation management",
    },
    member: {
        icon: UserRound,
        description: "Team participation",
    },
    committee: {
        icon: UsersRound,
        description: "Committee participation",
    },
    investor: {
        icon: Eye,
        description: "Investor access",
    },
};

type Props = {
    name: string;
    value: MembershipRole;
    options: MembershipRole[];
    disabled?: boolean;
    onChange: (role: MembershipRole) => void;
};

export function MemberRoleSelector({
    name,
    value,
    options,
    disabled = false,
    onChange,
}: Props) {
    const [open, setOpen] = useState(false);
    const rootRef = useRef<HTMLDivElement>(null);
    const menuRef = useRef<HTMLDivElement>(null);
    const id = useId();

    const selected = ROLE_DETAILS[value];
    const SelectedIcon = selected?.icon ?? ShieldCheck;

    useEffect(() => {
        if (!open) return;

        function handleOutside(event: PointerEvent) {
            if (
                event.target instanceof Node &&
                !rootRef.current?.contains(event.target)
            ) {
                setOpen(false);
            }
        }

        function handleEscape(event: globalThis.KeyboardEvent) {
            if (event.key === "Escape") {
                setOpen(false);
                rootRef.current
                    ?.querySelector<HTMLButtonElement>("[aria-haspopup]")
                    ?.focus();
            }
        }

        document.addEventListener("pointerdown", handleOutside);
        document.addEventListener("keydown", handleEscape);

        return () => {
            document.removeEventListener("pointerdown", handleOutside);
            document.removeEventListener("keydown", handleEscape);
        };
    }, [open]);

    function focusOption(index: number) {
        const buttons =
            menuRef.current?.querySelectorAll<HTMLButtonElement>(
                '[role="option"]',
            );

        if (!buttons?.length) return;

        const next = (index + buttons.length) % buttons.length;
        buttons[next]?.focus();
    }

    function handleMenuKeyDown(event: KeyboardEvent<HTMLDivElement>) {
        const buttons =
            menuRef.current?.querySelectorAll<HTMLButtonElement>(
                '[role="option"]',
            );

        if (!buttons?.length) return;

        const current = Array.from(buttons).findIndex(
            (button) => button === document.activeElement,
        );

        if (event.key === "ArrowDown") {
            event.preventDefault();
            focusOption(current + 1);
        } else if (event.key === "ArrowUp") {
            event.preventDefault();
            focusOption(current <= 0 ? buttons.length - 1 : current - 1);
        } else if (event.key === "Home") {
            event.preventDefault();
            focusOption(0);
        } else if (event.key === "End") {
            event.preventDefault();
            focusOption(buttons.length - 1);
        }
    }

    function selectRole(role: MembershipRole) {
        setOpen(false);

        rootRef.current
            ?.querySelector<HTMLButtonElement>("[aria-haspopup]")
            ?.focus();

        if (role !== value) {
            onChange(role);
        }
    }

    return (
        <div
            ref={rootRef}
            className="relative w-full min-w-0 sm:w-[205px]"
        >
            <button
                type="button"
                disabled={disabled}
                aria-label={`Role of ${name}: ${roleLabel(value)}`}
                aria-haspopup="listbox"
                aria-expanded={open}
                aria-controls={open ? id : undefined}
                onClick={() => setOpen((previous) => !previous)}
                onKeyDown={(event) => {
                    if (
                        !open &&
                        ["ArrowDown", "ArrowUp"].includes(event.key)
                    ) {
                        event.preventDefault();
                        setOpen(true);

                        requestAnimationFrame(() => {
                            focusOption(
                                event.key === "ArrowUp"
                                    ? options.length - 1
                                    : Math.max(options.indexOf(value), 0),
                            );
                        });
                    }
                }}
                className={`
          group flex min-h-11 w-full items-center gap-2.5
          rounded-xl border px-3 py-2.5 text-left
          font-sans text-sm font-semibold
          transition-all duration-200
          focus-visible:outline-2
          focus-visible:outline-offset-2
          focus-visible:outline-[#D7AD60]
          disabled:cursor-not-allowed disabled:opacity-60
          ${open
                        ? "border-[#D8AE65] bg-[#FFF9EE] shadow-[0_0_0_3px_rgba(221,180,104,0.13)]"
                        : "border-[#DCE5EF] bg-white hover:border-[#D8AE65] hover:bg-[#FFFCF6]"
                    }
        `}
            >
                <span
                    className="flex h-8 w-8 shrink-0 items-center justify-center
            rounded-lg border border-[#EBD8B5]
            bg-[#FCF4E7] text-[#A87934]"
                >
                    <SelectedIcon size={16} strokeWidth={1.8} />
                </span>

                <span className="min-w-0 flex-1 truncate text-[#142941]">
                    {roleLabel(value)}
                </span>

                <ChevronDown
                    size={16}
                    className={`shrink-0 text-[#8B9BAE]
            transition-transform duration-200
            ${open ? "rotate-180 text-[#B58A48]" : ""}`}
                />
            </button>

            {open && (

                <div
                    id={id}
                    ref={menuRef}
                    role="listbox"
                    aria-label={`Role of ${name}`}
                    onKeyDown={handleMenuKeyDown}

                    className="
                        iv-team-role-menu
                        absolute
                        top-[calc(100%+8px)]
                        z-50
                        rounded-2xl
                        border border-[#283D58]
                        bg-[#0D1D32]
                        p-2
                        shadow-[0_22px_55px_rgba(4,17,35,0.28)]
                    ">

                    <div className="border-b border-white/10 px-3 pb-3 pt-2">
                        <p className="font-sans text-[10px] font-bold uppercase tracking-[0.18em] text-[#E6BB70]">
                            Manage permissions
                        </p>
                        <p className="mt-1 font-sans text-xs text-[#9EADC2]">
                            Select a role for {name}
                        </p>
                    </div>

                    <div className="mt-1 space-y-1">
                        {options.map((role) => {
                            const detail = ROLE_DETAILS[role];
                            const Icon = detail?.icon ?? ShieldCheck;
                            const active = value === role;

                            return (
                                <button
                                    key={role}
                                    type="button"
                                    role="option"
                                    aria-label={roleLabel(role)}
                                    aria-selected={active}
                                    onClick={() => selectRole(role)}
                                    className={`flex w-full items-center gap-3
                    rounded-xl px-3 py-3 text-left
                    transition-colors duration-150
                    focus-visible:outline-2
                    focus-visible:outline-[#E6BB70]
                    ${active
                                            ? "bg-[#29394F]"
                                            : "hover:bg-white/[0.07]"
                                        }`}
                                >
                                    <span
                                        className={`flex h-10 w-10 shrink-0 items-center
                      justify-center rounded-xl border
                      ${active
                                                ? "border-[#D5A95E]/40 bg-[#D5A95E]/15 text-[#E6BB70]"
                                                : "border-white/10 bg-white/[0.05] text-[#B4C2D3]"
                                            }`}
                                    >
                                        <Icon size={18} strokeWidth={1.8} />
                                    </span>

                                    <span className="min-w-0 flex-1">
                                        <span className="block font-sans text-sm font-semibold text-white">
                                            {roleLabel(role)}
                                        </span>
                                        <span className="mt-0.5 block font-sans text-[11px] leading-4 text-[#9EADC2]">
                                            {detail?.description ?? "Organisation access"}
                                        </span>
                                    </span>

                                    {active && (
                                        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#E6BB70] text-[#0D1D32]">
                                            <Check size={14} strokeWidth={2.5} />
                                        </span>
                                    )}
                                </button>
                            );
                        })}
                    </div>

                    <div className="mt-2 flex items-center gap-2 border-t border-white/10 px-3 pb-1 pt-3 text-[11px] text-[#9EADC2]">
                        <ShieldCheck size={14} className="text-[#E6BB70]" />
                        Changes are saved to your organisation.
                    </div>
                </div>
            )}
        </div>
    );
}
