import type { Metadata } from "next";

import { IdeaForm } from "@/components/ideas/IdeaForm";

export const metadata: Metadata = {
  title: "New idea | InnoValuation",
};

export default function NewIdea() {
  return <IdeaForm />;
}
