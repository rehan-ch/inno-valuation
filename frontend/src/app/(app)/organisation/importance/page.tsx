import type { Metadata } from "next";

import { ImportancePage } from "@/components/organisation/ImportancePage";

export const metadata: Metadata = {
  title: "Dimension importance | InnoValuation",
};

export default function Importance() {
  return <ImportancePage />;
}
