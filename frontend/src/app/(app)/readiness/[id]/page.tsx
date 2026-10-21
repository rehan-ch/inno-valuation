import type { Metadata } from "next";

import { QuestionnairePage } from "@/components/readiness/QuestionnairePage";

export const metadata: Metadata = {
  title: "Readiness questions | InnoValuation",
};

export default async function Questionnaire({ params }: PageProps<"/readiness/[id]">) {
  const { id } = await params;
  return <QuestionnairePage assessmentId={id} />;
}
