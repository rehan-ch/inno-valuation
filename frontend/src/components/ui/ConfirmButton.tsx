"use client";

import { useState } from "react";

import { Button } from "./Button";

/** A destructive action that asks once, inline, before it runs. The question closes
 * again once the action has finished, whether it worked or not. */
export function ConfirmButton({
  label,
  confirmLabel,
  onConfirm,
  busy = false,
  disabled = false,
}: {
  label: string;
  confirmLabel: string;
  onConfirm: () => void;
  /** This action is running. */
  busy?: boolean;
  /** Another action is running, so this one must wait. */
  disabled?: boolean;
}) {
  const [confirming, setConfirming] = useState(false);
  const [wasBusy, setWasBusy] = useState(busy);
  if (wasBusy !== busy) {
    setWasBusy(busy);
    if (!busy) setConfirming(false);
  }

  if (!confirming) {
    return (
      <Button variant="danger" disabled={disabled} onClick={() => setConfirming(true)}>
        {label}
      </Button>
    );
  }
  return (
    <span className="inline-flex items-center gap-2">
      <Button variant="danger" busy={busy} disabled={disabled} onClick={onConfirm}>
        {confirmLabel}
      </Button>
      <Button variant="secondary" disabled={busy || disabled} onClick={() => setConfirming(false)}>
        Cancel
      </Button>
    </span>
  );
}
