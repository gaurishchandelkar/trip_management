import { type ReactNode, useEffect, useRef } from "react";

export interface DialogProps {
  open: boolean;
  /** Called when the dialog closes itself, such as on Escape. */
  onClose: () => void;
  /** The ID of the heading that names the dialog. */
  labelledBy: string;
  children: ReactNode;
}

/**
 * A native modal dialog. The browser traps focus, closes it on Escape and returns focus to the
 * element that opened it. Its content mounts only while open, so each opening starts fresh.
 */
export function Dialog({ open, onClose, labelledBy, children }: DialogProps) {
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const element = dialog.current;
    if (element === null) return;
    if (open && !element.open) {
      element.showModal();
      element.querySelector<HTMLElement>("input, button")?.focus();
    } else if (!open && element.open) {
      element.close();
    }
  }, [open]);

  return (
    <dialog ref={dialog} className="dialog" aria-labelledby={labelledBy} onClose={onClose}>
      {open && children}
    </dialog>
  );
}
