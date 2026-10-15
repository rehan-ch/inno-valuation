import type { Metadata } from "next";

import { ConsultantsPage } from "@/components/consultants/ConsultantsPage";

export const metadata: Metadata = {
  title: "Consultant access | InnoValuation",
};

export default function Consultants() {
  return <ConsultantsPage />;
}
