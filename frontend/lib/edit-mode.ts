/** Edit controls show in edit mode, and stay while an unsaved draft is open so it can be saved or cancelled. */
export function showEditControls(editMode: unknown, draftOpen: boolean): boolean {
  return editMode === true || draftOpen === true;
}

/** Only a real boolean `true` from stored preferences turns edit mode on; the default is user mode. */
export function storedEditMode(preferences: unknown): boolean {
  return typeof preferences === "object" && preferences !== null && (preferences as {editMode?: unknown}).editMode === true;
}
