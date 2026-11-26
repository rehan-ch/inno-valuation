
export const authButtonClass = [
    "group inline-flex h-12 w-full items-center justify-center gap-2",
    "!rounded-xl !bg-[#10243B] !text-white",
    "!shadow-[0_6px_18px_rgba(16,36,59,0.13)]",
    "transition-[background-color,box-shadow,transform] duration-200",
    "hover:!bg-[#1B3452]",
    "hover:!shadow-[0_10px_24px_rgba(16,36,59,0.18)]",
    "active:scale-[0.99]",
    "focus-visible:!outline-2",
    "focus-visible:!outline-offset-2",
    "focus-visible:!outline-[#304E73]",
    "disabled:!bg-[#8190A1] disabled:!shadow-none",
    "disabled:!cursor-not-allowed",
    "motion-reduce:transform-none",
].join(" ");

export const authLinkClass = [
    "font-semibold text-[#183C64]",
    "transition-colors duration-200",
    "hover:text-[#315D89] hover:underline",
    "focus-visible:rounded-sm focus-visible:outline-2",
    "focus-visible:outline-offset-2",
    "focus-visible:outline-[#315D89]",
].join(" ");

export const authSecondaryLinkClass = [
    "inline-flex min-h-10 items-center justify-center gap-2",
    "text-sm font-semibold text-[#183C64]",
    "transition-colors hover:text-[#315D89] hover:underline",
    "focus-visible:rounded-sm focus-visible:outline-2",
    "focus-visible:outline-offset-2",
    "focus-visible:outline-[#315D89]",
].join(" ");
