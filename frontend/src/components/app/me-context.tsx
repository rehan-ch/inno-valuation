"use client";

import { createContext, useContext } from "react";
import type { ReactNode } from "react";

import type { MeOut } from "@/lib/api/types";

export interface MeContextValue {
  me: MeOut;
  /** Replace the cached account, e.g. with the response of a call that returns MeOut. */
  update: (me: MeOut) => void;
  /** Re-read /me from the server. */
  refresh: () => Promise<void>;
}

const MeContext = createContext<MeContextValue | null>(null);

export function MeProvider({ value, children }: { value: MeContextValue; children: ReactNode }) {
  return <MeContext.Provider value={value}>{children}</MeContext.Provider>;
}

export function useMe(): MeContextValue {
  const value = useContext(MeContext);
  if (value === null) throw new Error("useMe needs a MeProvider above it.");
  return value;
}
