"use client";
import {useCallback, useEffect, useRef, useState} from "react";
import {searchRequest, searchEngineRequest, externalSearchUrl, type SearchResponse, type SearchEngine} from "../lib/search";
import {Modal} from "./modal";
import {SearchEngineManager} from "./search-engine-manager";
import "./global-search.css";

export function GlobalSearch({onNavigate, csrfToken}: {onNavigate: (route: string, dashboardId?: string) => void; csrfToken: string}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState<SearchResponse>({results: [], warnings: []});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [engines, setEngines] = useState<SearchEngine[]>([]);
  const [engineError, setEngineError] = useState("");
  const [managing, setManaging] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault(); setOpen(value => !value);
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  useEffect(() => { if (open) {input.current?.focus();} else {setQuery(""); setResponse({results: [], warnings: []}); setError(""); setManaging(false);} }, [open, managing]);
  const loadEngines = useCallback(async () => {
    try {setEngines((await searchEngineRequest()).engines); setEngineError("");}
    catch {setEngines([]); setEngineError("Je zoekmachines zijn tijdelijk niet beschikbaar.");}
  }, []);
  useEffect(() => {if (open) void loadEngines();}, [open, loadEngines]);
  useEffect(() => {
    if (!open || !query.trim()) {setResponse({results: [], warnings: []}); setLoading(false); return;}
    const controller = new AbortController();
    setLoading(true); setError(""); setResponse({results: [], warnings: []});
    const timer = setTimeout(() => {
      void searchRequest(query, controller.signal).then(value => {if (!controller.signal.aborted) setResponse(value);})
        .catch(() => {if (!controller.signal.aborted) setError("Zoeken is tijdelijk niet beschikbaar. Pas je zoekterm aan of probeer opnieuw.");})
        .finally(() => {if (!controller.signal.aborted) setLoading(false);});
    }, 200);
    return () => {clearTimeout(timer); controller.abort();};
  }, [query, open]);
  return <>
    <button className="cd-search-open" onClick={() => setOpen(true)} aria-label="Zoeken in ControlDeck">Zoeken <kbd>Ctrl K</kbd></button>
    <Modal open={open} title={managing ? "Zoekmachines beheren" : "Zoeken in ControlDeck"} onClose={() => setOpen(false)}>
      {managing ? <><SearchEngineManager engines={engines} csrfToken={csrfToken} onChanged={loadEngines} onBack={() => setManaging(false)}/>{engineError && <p role="status">{engineError}</p>}</> : <div className="cd-search"><label>Zoek apps, dashboards en onderdelen<input ref={input} type="search" autoComplete="off" maxLength={200} value={query} onChange={event => setQuery(event.target.value)}/></label>
        <p role="status">{loading ? "Zoeken…" : !query.trim() ? "Typ een naam of groep om te zoeken." : !response.results.length && !error ? "Geen resultaten gevonden." : `${response.results.length} resultaten`}</p>
        {error && <p role="alert" className="config-error">{error}</p>}
        {response.warnings.map(warning => <p key={warning} role="status">{warning}</p>)}
        <ul>{response.results.map(result => <li key={result.id}>{result.kind === "app" ? <a href={result.url} target="_blank" rel="noopener noreferrer" onClick={() => setOpen(false)}><strong>{result.title} ↗</strong><span>{result.description}</span><small>App</small></a> : <button onClick={() => {setOpen(false); onNavigate(result.route, result.kind === "dashboard" ? result.dashboardId : undefined);}}><strong>{result.title}</strong><span>{result.description}</span><small>{result.kind === "dashboard" ? "Dashboard" : "Onderdeel"}</small></button>}</li>)}</ul>
        {query.trim() && engines.length > 0 && <><p>Extern zoeken · alleen na je keuze</p><ul>{engines.map(engine => <li key={engine.id}><a href={externalSearchUrl(engine, query)} target="_blank" rel="noopener noreferrer" onClick={() => setOpen(false)}>Zoek met {engine.name} ↗</a></li>)}</ul></>}
        {engineError && <p role="status">{engineError}</p>}<button onClick={() => setManaging(true)}>Zoekmachines beheren</button>
      </div>}
    </Modal>
  </>;
}
