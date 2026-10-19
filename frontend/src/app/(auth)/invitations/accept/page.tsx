import type { Metadata } from "next";

import { AcceptInvitation } from "@/components/auth/AcceptInvitation";

export const metadata: Metadata = {
  title: "Join an organisation | InnoValuation",
};

export default function AcceptInvitationPage() {
  return <AcceptInvitation />;
}
