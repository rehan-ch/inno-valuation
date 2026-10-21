import type { Metadata } from "next";

import { ReadinessListPage } from "@/components/readiness/ReadinessListPage";

export const metadata: Metadata = {
  title: "Readiness | InnoValuation",
};

export default function Readiness() {
  return <ReadinessListPage />;
}
