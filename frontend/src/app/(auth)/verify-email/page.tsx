import type { Metadata } from "next";

import { VerifyEmail } from "@/components/auth/VerifyEmail";

export const metadata: Metadata = {
  title: "Confirm your email | InnoValuation",
};

export default function VerifyEmailPage() {
  return <VerifyEmail />;
}
