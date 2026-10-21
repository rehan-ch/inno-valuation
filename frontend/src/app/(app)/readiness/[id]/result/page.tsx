import type { Metadata } from "next";

import { ResultPage } from "@/components/readiness/ResultPage";

export const metadata: Metadata = {
  title: "Readiness result | InnoValuation",
};

export default async function Result({ params }: PageProps<"/readiness/[id]/result">) {
  const { id } = await params;
  return <ResultPage assessmentId={id} />;
}
