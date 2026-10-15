import type { Metadata } from "next";

import { SignUpForm } from "@/components/auth/SignUpForm";

export const metadata: Metadata = {
  title: "Create an account | InnoValuation",
};

export default function SignUpPage() {
  return <SignUpForm />;
}
