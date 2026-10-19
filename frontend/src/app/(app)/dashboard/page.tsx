import type { Metadata } from "next";

import { DashboardPage } from "@/components/dashboard/DashboardPage";

export const metadata: Metadata = {
  title: "Dashboard | InnoValuation",
};

export default function Dashboard() {
  return <DashboardPage />;
}
