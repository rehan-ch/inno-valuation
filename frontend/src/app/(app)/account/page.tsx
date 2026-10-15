import type { Metadata } from "next";

import { AccountPage } from "@/components/account/AccountPage";

export const metadata: Metadata = {
  title: "Account | InnoValuation",
};

export default function Account() {
  return <AccountPage />;
}
