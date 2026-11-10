import type { Metadata } from "next";
import { Suspense } from "react";

import { HistoryPage } from "@/components/history/HistoryPage";
import { Loading } from "@/components/ui/Loading";

export const metadata: Metadata = {
  title: "History | InnoValuation",
};

export default function History() {
  return (
    <Suspense fallback={<Loading>Loading the history...</Loading>}>
      <HistoryPage />
    </Suspense>
  );
}
