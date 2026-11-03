import type { Metadata } from "next";

import { IdeasListPage } from "@/components/ideas/IdeasListPage";

export const metadata: Metadata = {
  title: "Ideas | InnoValuation",
};

export default function Ideas() {
  return <IdeasListPage />;
}
