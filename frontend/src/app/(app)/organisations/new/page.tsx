import type { Metadata } from "next";

import { NewOrganisationForm } from "@/components/organisation/NewOrganisationForm";

export const metadata: Metadata = {
  title: "New organisation | InnoValuation",
};

export default function NewOrganisationPage() {
  return <NewOrganisationForm />;
}
