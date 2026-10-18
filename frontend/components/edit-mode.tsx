"use client";
import {createContext, useContext} from "react";

/** Global user/edit mode: in user mode pages hide their edit and management controls. */
export const EditModeContext = createContext(false);
export function useEditMode(): boolean { return useContext(EditModeContext); }

export function EditModeSwitch({on, label, onChange}: {on: boolean; label: string; onChange: (on: boolean) => void}) {
  return <button type="button" role="switch" aria-checked={on} className="edit-mode-switch" onClick={() => onChange(!on)}>
    <span className="edit-mode-icon" aria-hidden="true">✎</span>{label}<span className="edit-mode-track" aria-hidden="true"><span/></span>
  </button>;
}
