import type { Metadata } from "next";

import { ResetPasswordForm } from "@/components/auth/ResetPasswordForm";

export const metadata: Metadata = {
  title: "Reset password | InnoValuation",
};

export default function ResetPasswordPage() {
  return <ResetPasswordForm />;
}
