"use client";

import { useEffect, useRef } from "react";
import type { MouseEvent, ReactNode } from "react";

interface DialogProps {
  open: boolean;
  /** Called when the user closes the dialog (Escape, backdrop or the close button).
   * The parent owns the open state, so it must set `open` to false here. */
  onClose: () => void;
  title: string;
  children: ReactNode;
}

function BaseDialog({ open, onClose, title, children, panelClass }: DialogProps & { panelClass: string }) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  function handleBackdropClick(event: MouseEvent<HTMLDialogElement>) {
    // Only a click on the backdrop targets the dialog element itself. The padding
    // lives on an inner div, so a click inside the panel never matches.
    if (event.target === ref.current) onClose();
  }

  return (
    <dialog
      ref={ref}
      aria-label={title}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={handleBackdropClick}
      className={panelClass}
    >
      <div className="p-6">
        <div className="flex items-start justify-between gap-4">
          <h2 className="text-base font-semibold text-neutral-900">{title}</h2>
          <button
            type="button"
            aria-label="Close"
            onClick={onClose}
            className="-mt-1 -mr-1 rounded-md p-1 text-neutral-500 hover:bg-neutral-100 hover:text-neutral-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neutral-900"
          >
            <span aria-hidden="true" className="block text-lg leading-none">
              &times;
            </span>
          </button>
        </div>
        <div className="mt-4">{children}</div>
      </div>
    </dialog>
  );
}

/** A centred dialog on the native <dialog> element: the browser traps focus and
 * handles Escape; the backdrop and the close button also close it. */
export function Modal(props: DialogProps) {
  return (
    <BaseDialog
      {...props}
      panelClass="m-auto w-full max-w-md rounded-lg border border-neutral-200 bg-white shadow-lg backdrop:bg-neutral-900/50"
    />
  );
}

/** A panel that docks to the right edge, for side content on larger screens.
 * Same behaviour as Modal, different placement. */
export function Drawer(props: DialogProps) {
  return (
    <BaseDialog
      {...props}
      panelClass="m-0 ml-auto h-dvh max-h-none w-full max-w-sm overflow-y-auto border-l border-neutral-200 bg-white shadow-lg backdrop:bg-neutral-900/50"
    />
  );
}
