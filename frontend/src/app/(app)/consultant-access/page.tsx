import type { Metadata } from "next";

import { MyAccessPage } from "@/components/consultants/MyAccessPage";

export const metadata: Metadata = {
  title: "My consulting access | InnoValuation",
};

export default function ConsultantAccessPage() {
  return <MyAccessPage />;
}
