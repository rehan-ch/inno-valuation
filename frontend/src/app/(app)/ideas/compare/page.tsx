import type { Metadata } from "next";
import { Suspense } from "react";

import { ComparePage } from "@/components/ideas/ComparePage";
import { Loading } from "@/components/ui/Loading";

export const metadata: Metadata = {
  title: "Compare ideas | InnoValuation",
};

export default function Compare() {
  return (
    <Suspense fallback={<Loading>Loading the comparison...</Loading>}>
      <ComparePage />
    </Suspense>
  );
}
