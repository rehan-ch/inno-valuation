import type { Metadata } from "next";
import { Suspense } from "react";

import { DimensionPage } from "@/components/dimensions/DimensionPage";
import { Loading } from "@/components/ui/Loading";

export const metadata: Metadata = {
  title: "Dimension | InnoValuation",
};

export default async function Dimension({ params }: PageProps<"/dimensions/[key]">) {
  const { key } = await params;
  return (
    <Suspense fallback={<Loading>Loading the dimension...</Loading>}>
      <DimensionPage dimensionKey={key} />
    </Suspense>
  );
}
