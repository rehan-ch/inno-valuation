import type { Metadata } from "next";

import { AssessmentPage } from "@/components/ideas/AssessmentPage";

export const metadata: Metadata = {
  title: "Innovation Quotient | InnoValuation",
};

export default async function Assessment({
  params,
}: PageProps<"/ideas/[id]/assessments/[assessmentId]">) {
  const { id, assessmentId } = await params;
  return <AssessmentPage ideaId={id} assessmentId={assessmentId} />;
}
