import type { ReactNode } from "react";

type Tone = "error" | "success" | "info";

const TONES: Record<Tone, string> = {
  error: "border-red-200 bg-red-50 text-red-900",
  success: "border-emerald-200 bg-emerald-50 text-emerald-900",
  info: "border-neutral-200 bg-white text-neutral-700",
};

export function Alert({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={`rounded-md border px-3.5 py-3 text-sm ${TONES[tone]}`}
    >
      {children}
    </div>
  );
}
