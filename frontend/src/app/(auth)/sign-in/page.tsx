import type { Metadata } from "next";

import { SignInForm } from "@/components/auth/SignInForm";

export const metadata: Metadata = {
  title: "Sign in | InnoValuation",
};

export default function SignInPage() {
  return <SignInForm />;
}
