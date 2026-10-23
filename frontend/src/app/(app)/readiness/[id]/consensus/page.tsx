import type { Metadata } from "next";

import { ConsensusPage } from "@/components/readiness/ConsensusPage";

export const metadata: Metadata = {
  title: "Agree the answers | InnoValuation",
};

export default async function Consensus({ params }: PageProps<"/readiness/[id]/consensus">) {
  const { id } = await params;
  return <ConsensusPage assessmentId={id} />;
}
