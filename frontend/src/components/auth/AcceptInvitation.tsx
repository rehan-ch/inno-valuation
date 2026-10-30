"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button, buttonClass } from "@/components/ui/Button";
import { Loading } from "@/components/ui/Loading";
import { signOut } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import { getMe } from "@/lib/api/me";
import { acceptInvitation, previewInvitation } from "@/lib/api/team";
import type { InvitationPreviewOut, MeOut } from "@/lib/api/types";
import { formatDate } from "@/lib/format";
import { readHashToken } from "@/lib/hash-token";
import { useSubmit } from "@/lib/forms";
import { roleWithArticle } from "@/lib/roles";

type State =
  | { kind: "checking" }
  | { kind: "no_token" }
  | { kind: "failed"; message: string }
  | { kind: "ready"; token: string; preview: InvitationPreviewOut; me: MeOut | null };

/** The page an invitation email links to. The token stays in the URL fragment, so a
 * visitor can sign in (the fragment follows them) and come back to accept. */
export function AcceptInvitation() {
  const [state, setState] = useState<State>({ kind: "checking" });
  const { busy, error, run } = useSubmit();
  const router = useRouter();

  useEffect(() => {
    const token = readHashToken();
    if (!token) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time read of the URL fragment, only possible after mount
      setState({ kind: "no_token" });
      return;
    }
    async function load(token: string) {
      try {
        const preview = await previewInvitation(token);
        const me = await getMe().catch((err: unknown) => {
          if (err instanceof ApiError && err.status === 401) return null;
          throw err;
        });
        setState({ kind: "ready", token, preview, me });
      } catch (err) {
        setState({
          kind: "failed",
          message:
            err instanceof ApiError ? err.message : "Something went wrong. Try the link again.",
        });
      }
    }
    void load(token);
  }, []);

  async function handleAccept(token: string) {
    const me = await run(() => acceptInvitation(token));
    if (me) router.push("/dashboard");
  }

  async function handleSwitchAccount() {
    const result = await run(() => signOut());
    if (!result) return; // the error shows in the alert; staying signed in must be visible
    // Keep the fragment: after signing in with the right account, the token is still there.
    router.push(`/sign-in?next=%2Finvitations%2Faccept${window.location.hash}`);
  }

  if (state.kind === "checking") {
    return <Loading>Checking the invitation...</Loading>;
  }

  if (state.kind === "no_token" || state.kind === "failed") {
    return (
      <div className="space-y-4">
        <h1 className="text-lg font-semibold text-neutral-900">Join an organisation</h1>
        <Alert tone="error">
          {state.kind === "failed"
            ? state.message
            : "This page needs the link from an invitation email."}
        </Alert>
        <p className="text-sm text-neutral-600">
          Ask the person who invited you to send a new invitation if the link has expired.
        </p>
      </div>
    );
  }

  const { token, preview, me } = state;
  const header = (
    <>
      <h1 className="text-lg font-semibold text-neutral-900">Join {preview.organisation_name}</h1>
      <p className="text-sm text-neutral-600">
        {preview.email} is invited to join <strong>{preview.organisation_name}</strong> as{" "}
        <strong>{roleWithArticle(preview.role)}</strong>. The invitation is valid until{" "}
        {formatDate(preview.expires_at)}.
      </p>
    </>
  );

  if (me === null) {
    return (
      <div className="space-y-4">
        {header}
        <p className="text-sm text-neutral-600">
          Sign in as {preview.email} to accept. New here? Create an account with that email first,
          confirm it, then open this link again.
        </p>
        <div className="flex gap-2">
          <Link
            href={`/sign-in?next=%2Finvitations%2Faccept#token=${encodeURIComponent(token)}`}
            className={buttonClass("primary")}
          >
            Sign in
          </Link>
          <Link
            href="/sign-up"
            className={buttonClass("secondary")}
          >
            Create an account
          </Link>
        </div>
      </div>
    );
  }

  if (me.email !== preview.email) {
    return (
      <div className="space-y-4">
        {header}
        <Alert tone="error">
          This invitation is for {preview.email}, but you are signed in as {me.email}. Sign out and
          sign in with the invited email.
        </Alert>
        {error && <Alert tone="error">{error.message}</Alert>}
        <Button variant="secondary" busy={busy} onClick={() => void handleSwitchAccount()}>
          Sign out and switch account
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {header}
      {error && <Alert tone="error">{error.message}</Alert>}
      <Button busy={busy} className="w-full" onClick={() => void handleAccept(token)}>
        Accept invitation
      </Button>
    </div>
  );
}
