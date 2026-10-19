"use client";

import { useState } from "react";
import type { FormEvent } from "react";

import { useMe } from "@/components/app/me-context";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardTitle, PageHeader } from "@/components/ui/Card";
import { TextField } from "@/components/ui/fields";
import { changePassword, updateName } from "@/lib/api/me";
import { newPasswordError, useSubmit } from "@/lib/forms";

export function AccountPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="Account" />
      <ProfileCard />
      <PasswordCard />
    </div>
  );
}

function ProfileCard() {
  const { me, update } = useMe();
  const { busy, error, run } = useSubmit();
  const [name, setName] = useState(me.name);
  const [saved, setSaved] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSaved(false);
    const result = await run(() => updateName(name));
    if (result) {
      update(result);
      setSaved(true);
    }
  }

  return (
    <Card>
      <CardTitle>Profile</CardTitle>
      <form onSubmit={(e) => void handleSubmit(e)} className="mt-4 max-w-md space-y-4" noValidate>
        {error && <Alert tone="error">{error.message}</Alert>}
        {saved && <Alert tone="success">Your name is saved.</Alert>}
        <TextField
          label="Name"
          name="name"
          autoComplete="name"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <TextField label="Email" type="email" name="email" value={me.email} disabled readOnly />
        <Button type="submit" busy={busy}>
          Save
        </Button>
      </form>
    </Card>
  );
}

function PasswordCard() {
  const { busy, error, run } = useSubmit();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [nextError, setNextError] = useState<string | undefined>(undefined);
  const [doneMessage, setDoneMessage] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setDoneMessage(null);
    const invalid = newPasswordError(next);
    if (invalid) {
      setNextError(invalid);
      return;
    }
    const result = await run(() => changePassword(current, next));
    if (result) {
      setDoneMessage(result.message);
      setCurrent("");
      setNext("");
    }
  }

  return (
    <Card>
      <CardTitle>Change password</CardTitle>
      <p className="mt-1 text-sm text-neutral-600">
        Changing your password signs you out everywhere else.
      </p>
      <form onSubmit={(e) => void handleSubmit(e)} className="mt-4 max-w-md space-y-4" noValidate>
        {error && <Alert tone="error">{error.message}</Alert>}
        {doneMessage && <Alert tone="success">{doneMessage}</Alert>}
        <TextField
          label="Current password"
          type="password"
          name="current_password"
          autoComplete="current-password"
          required
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
        />
        <TextField
          label="New password"
          type="password"
          name="new_password"
          autoComplete="new-password"
          required
          minLength={8}
          error={nextError}
          value={next}
          onChange={(e) => {
            const value = e.target.value;
            setNext(value);
            // Once shown, the length message stays until the password reaches 8.
            setNextError((prev) => (prev ? newPasswordError(value) : undefined));
          }}
        />
        <Button type="submit" busy={busy}>
          Change password
        </Button>
      </form>
    </Card>
  );
}
