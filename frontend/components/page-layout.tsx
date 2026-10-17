"use client";
import "./editable-grid.css";
import {useCallback, useEffect, useState} from "react";
import {pageLayoutRequest, type LayoutPage, type PageLayoutCell} from "../lib/page-layouts";

/** Personal layout of one page: view mode uses the saved cells, edit mode a draft saved with Opslaan. */
export function usePageLayout(page: LayoutPage, csrfToken: string) {
  const [saved, setSaved] = useState<PageLayoutCell[]>([]);
  const [draft, setDraft] = useState<PageLayoutCell[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    pageLayoutRequest(page, "", "GET", undefined, controller.signal).then(setSaved).catch(failure => { if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : "Indeling niet beschikbaar."); })
      .finally(() => { if (!controller.signal.aborted) setLoaded(true); });
    return () => controller.abort();
  }, [page]);
  useEffect(() => {
    if (!draft) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [draft]);
  const run = async (action: () => Promise<void>) => {
    setBusy(true); setError("");
    try { await action(); } catch (failure) { setError(failure instanceof Error ? failure.message : "Opslaan mislukt."); } finally { setBusy(false); }
  };
  return {
    cells: draft ?? saved, editing: !!draft, busy, error, loaded,
    /** Start with the merged cells currently on screen so nothing jumps when editing begins. */
    edit: useCallback((current: PageLayoutCell[]) => { setDraft(current); setError(""); }, []),
    change: setDraft as (cells: PageLayoutCell[]) => void,
    cancel: () => { setDraft(null); setError(""); },
    save: (cells: PageLayoutCell[]) => run(async () => { setSaved(await pageLayoutRequest(page, csrfToken, "PUT", cells)); setDraft(null); }),
    reset: () => run(async () => { await pageLayoutRequest(page, csrfToken, "DELETE"); setSaved([]); setDraft(null); }),
  };
}

export function LayoutToolbar({editing, busy, error, onEdit, onSave, onCancel, onReset}: {editing: boolean; busy: boolean; error: string; onEdit: () => void; onSave: () => void; onCancel: () => void; onReset: () => void}) {
  return <div className="cd-layout-toolbar">
    {editing ? <>
      <span role="status">Bewerkmodus · sleep ⠿ om te verplaatsen en ↘ om te vergroten of verkleinen.</span>
      <button className="cd-layout-primary" disabled={busy} onClick={onSave}>{busy ? "Opslaan…" : "Opslaan"}</button>
      <button disabled={busy} onClick={onCancel}>Annuleren</button>
      <button disabled={busy} onClick={() => { if (window.confirm("Standaardindeling herstellen? Je eigen indeling van deze pagina vervalt.")) onReset(); }}>Standaard herstellen</button>
    </> : <button disabled={busy} onClick={onEdit}>Indeling aanpassen</button>}
    {error && <p role="alert" className="config-error">{error}</p>}
  </div>;
}
