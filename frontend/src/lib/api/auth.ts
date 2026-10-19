// /api/v1/auth: sign-up, email verification, sign-in and password recovery.
import { postJson } from "./client";
import type { MeOut, MessageOut } from "./types";

export function signUp(input: {
  name: string;
  email: string;
  password: string;
  accepted_terms: true;
}): Promise<MessageOut> {
  return postJson("/auth/sign-up", input);
}

export function verifyEmail(input: { token: string; password?: string }): Promise<MessageOut> {
  return postJson("/auth/verify-email", input);
}

export function resendVerification(email: string): Promise<MessageOut> {
  return postJson("/auth/verify-email/resend", { email });
}

export function signIn(email: string, password: string): Promise<MeOut> {
  return postJson("/auth/sign-in", { email, password });
}

export function signOut(): Promise<MessageOut> {
  return postJson("/auth/sign-out");
}

export function forgotPassword(email: string): Promise<MessageOut> {
  return postJson("/auth/password/forgot", { email });
}

export function resetPassword(token: string, newPassword: string): Promise<MessageOut> {
  return postJson("/auth/password/reset", { token, new_password: newPassword });
}
