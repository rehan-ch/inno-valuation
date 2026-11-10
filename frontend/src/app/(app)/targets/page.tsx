import type { Metadata } from "next";

import { TargetsPage } from "@/components/targets/TargetsPage";

export const metadata: Metadata = {
  title: "Targets | InnoValuation",
};

export default function Targets() {
  return <TargetsPage />;
}
