import type { Metadata } from "next";

import { OrganisationSettings } from "@/components/organisation/OrganisationSettings";

export const metadata: Metadata = {
  title: "Organisation settings | InnoValuation",
};

export default function Organisation() {
  return <OrganisationSettings />;
}
