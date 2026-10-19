"use client";

import { useState } from "react";

import { Button } from "./Button";

/** A destructive action that asks once, inline, before it runs. */
export function ConfirmButton({
  label,
  confirmLabel,
  onConfirm,
  busy = false,
}: {
  label: string;
  confirmLabel: string;
  onConfirm: () => void;
  busy?: boolean;
}) {
  const [confirming, setConfirming] = useState(false);

  if (!confirming) {
    return (
      <Button variant="danger" onClick={() => setConfirming(true)}>
        {label}
      </Button>
    );
  }
  return (
    <span className="inline-flex items-center gap-2">
      <Button variant="danger" busy={busy} onClick={onConfirm}>
        {confirmLabel}
      </Button>
      <Button variant="secondary" disabled={busy} onClick={() => setConfirming(false)}>
        Cancel
      </Button>
    </span>
  );
}
