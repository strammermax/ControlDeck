"use client";
import { useEffect, useId, useRef, type ReactNode } from "react";

/**
 * Accessible modal popup on the native <dialog>: focus moves into the dialog and returns afterwards,
 * Escape closes it, the page behind it is inert. Clicking the backdrop closes it as well.
 */
export function Modal({ open, title, onClose, children }: { open: boolean; title: string; onClose: () => void; children: ReactNode }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (open && !element.open) element.showModal();
    if (!open && element.open) element.close();
  }, [open]);
  return <dialog ref={dialog} className="modal" aria-labelledby={titleId}
    onCancel={event => { event.preventDefault(); onClose(); }}
    onClick={event => { if (event.target === event.currentTarget) onClose(); }}>
    <div className="modal-content">
      <header className="modal-header"><h3 id={titleId}>{title}</h3><button type="button" className="modal-close" onClick={onClose} aria-label="Sluiten">✕</button></header>
      {open && children}
    </div>
  </dialog>;
}
