import type { Metadata } from "next";

import { ActivityPage } from "@/components/organisation/ActivityPage";

export const metadata: Metadata = {
  title: "Activity log | InnoValuation",
};

export default function Activity() {
  return <ActivityPage />;
}
