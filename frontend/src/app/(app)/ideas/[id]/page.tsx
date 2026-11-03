import type { Metadata } from "next";

import { IdeaPage } from "@/components/ideas/IdeaPage";

export const metadata: Metadata = {
  title: "Idea | InnoValuation",
};

export default async function Idea({ params }: PageProps<"/ideas/[id]">) {
  const { id } = await params;
  return <IdeaPage ideaId={id} />;
}
