"use client";
import {useState} from "react";
import {externalSearchUrl, searchEngineRequest, type SearchEngine} from "../lib/search";

export function SearchEngineManager({engines, csrfToken, onChanged, onBack}: {engines: SearchEngine[]; csrfToken: string; onChanged: () => Promise<void>; onBack: () => void}) {
  const [form, setForm] = useState({name: "", urlTemplate: ""});
  const [editing, setEditing] = useState<SearchEngine | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const mutate = async (remove = false) => {
    setBusy(true); setError(""); setMessage("");
    try {
      if (!remove) externalSearchUrl(form, "query");
      await searchEngineRequest(editing ? `/${editing.id}` : "", csrfToken, remove ? "DELETE" : editing ? "PUT" : "POST", remove ? {revision: editing!.revision} : {...form, ...(editing ? {revision: editing.revision} : {})});
      await onChanged(); setEditing(null); setForm({name: "", urlTemplate: ""}); setMessage(remove ? "Zoekmachine verwijderd." : "Zoekmachine opgeslagen.");
    } catch (failure) {setError(failure instanceof Error ? failure.message : "Opslaan mislukt.");}
    finally {setBusy(false);}
  };
  return <div className="cd-search">
    <p>Voeg bijvoorbeeld je SearXNG of een werkportaal toe. Gebruik precies één <code>%s</code> waar de zoekterm hoort. Er wordt pas extern gezocht wanneer je een zoeklink kiest.</p>
    <ul>{engines.map(engine => <li key={engine.id}><button disabled={busy} onClick={() => {setEditing(engine); setForm({name: engine.name, urlTemplate: engine.urlTemplate}); setError(""); setMessage("");}}><strong>{engine.name}</strong><span>Aanpassen</span></button></li>)}</ul>
    <form className="cd-search-engine-form" onSubmit={event => {event.preventDefault(); void mutate();}}>
      <label>Naam<input required maxLength={80} disabled={busy} value={form.name} onChange={event => setForm({...form, name: event.target.value})}/></label>
      <label>Zoekadres met %s<input required type="text" maxLength={2048} disabled={busy} placeholder="https://zoeken.example.test/search?q=%s" value={form.urlTemplate} onChange={event => setForm({...form, urlTemplate: event.target.value})}/></label>
      <div className="cd-search-actions"><button disabled={busy || (!editing && engines.length >= 10)} type="submit">{busy ? "Bezig…" : "Zoekmachine opslaan"}</button>{editing && <><button disabled={busy} type="button" onClick={() => {setEditing(null); setForm({name: "", urlTemplate: ""});}}>Nieuw</button><button disabled={busy} type="button" onClick={() => {if (window.confirm(`Zoekmachine ‘${editing.name}’ verwijderen?`)) void mutate(true);}}>Verwijderen</button></>}</div>
    </form>
    {error && <p role="alert" className="config-error">{error}</p>}{message && <p role="status">{message}</p>}
    <button disabled={busy} onClick={onBack}>Terug naar zoeken</button>
  </div>;
}
