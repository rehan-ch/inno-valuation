import type { Metadata } from "next";

import { TeamPage } from "@/components/team/TeamPage";

export const metadata: Metadata = {
  title: "Team | InnoValuation",
};

export default function Team() {
  return <TeamPage />;
}
