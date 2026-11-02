import type { Metadata } from "next";

import { IdeaForm } from "@/components/ideas/IdeaForm";

export const metadata: Metadata = {
  title: "Edit idea | InnoValuation",
};

export default async function EditIdea({ params }: PageProps<"/ideas/[id]/edit">) {
  const { id } = await params;
  return <IdeaForm ideaId={id} />;
}
