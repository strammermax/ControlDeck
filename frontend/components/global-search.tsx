"use client";
import {useCallback, useEffect, useRef, useState} from "react";
import {searchRequest, searchEngineRequest, externalSearchUrl, type SearchResponse, type SearchEngine} from "../lib/search";
import {Modal} from "./modal";
import {SearchEngineManager} from "./search-engine-manager";
import "./global-search.css";

/** Search field in the top bar; results open in a panel underneath. Ctrl/Cmd+K focuses it, Esc closes. */
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
  const box = useRef<HTMLDivElement>(null);
  const close = useCallback(() => { setOpen(false); setQuery(""); input.current?.blur(); }, []);
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); input.current?.focus(); setOpen(true); }
    };
    const outside = (event: PointerEvent) => { if (box.current && !box.current.contains(event.target as Node)) setOpen(false); };
    window.addEventListener("keydown", key);
    document.addEventListener("pointerdown", outside);
    return () => { window.removeEventListener("keydown", key); document.removeEventListener("pointerdown", outside); };
  }, []);
  const loadEngines = useCallback(async () => {
    try {setEngines((await searchEngineRequest()).engines); setEngineError("");}
    catch {setEngines([]); setEngineError("Je zoekmachines zijn tijdelijk niet beschikbaar.");}
  }, []);
  useEffect(() => {if (open || managing) void loadEngines();}, [open, managing, loadEngines]);
  useEffect(() => {
    if (!query.trim()) {setResponse({results: [], warnings: []}); setLoading(false); setError(""); return;}
    const controller = new AbortController();
    setLoading(true); setError("");
    const timer = setTimeout(() => {
      void searchRequest(query, controller.signal).then(value => {if (!controller.signal.aborted) setResponse(value);})
        .catch(() => {if (!controller.signal.aborted) setError("Zoeken is tijdelijk niet beschikbaar. Pas je zoekterm aan of probeer opnieuw.");})
        .finally(() => {if (!controller.signal.aborted) setLoading(false);});
    }, 200);
    return () => {clearTimeout(timer); controller.abort();};
  }, [query]);
  const go = (route: string, dashboardId?: string) => { close(); onNavigate(route, dashboardId); };
  const first = response.results[0];
  return <div className="cd-searchbar" ref={box}>
    <input ref={input} type="search" autoComplete="off" maxLength={200} value={query} placeholder="Zoeken…" aria-label="Zoek apps, dashboards en onderdelen"
      aria-expanded={open && !!query.trim()} aria-controls="cd-search-results"
      onFocus={() => setOpen(true)} onChange={event => {setQuery(event.target.value); setOpen(true);}}
      onKeyDown={event => {
        if (event.key === "Escape") { event.preventDefault(); close(); }
        else if (event.key === "Enter" && first) {
          event.preventDefault();
          if (first.kind === "app") { window.open(first.url, "_blank", "noopener,noreferrer"); close(); } else go(first.route, first.kind === "dashboard" ? first.dashboardId : undefined);
        }
      }}/>
    {!query && <kbd aria-hidden="true">Ctrl K</kbd>}
    {open && query.trim() && <div className="cd-search cd-search-panel" id="cd-search-results">
      <p role="status">{loading ? "Zoeken…" : !response.results.length && !error ? "Geen resultaten gevonden." : `${response.results.length} resultaten`}</p>
      {error && <p role="alert" className="config-error">{error}</p>}
      {response.warnings.map(warning => <p key={warning} role="status">{warning}</p>)}
      <ul>{response.results.map(result => <li key={result.id}>{result.kind === "app" ? <a href={result.url} target="_blank" rel="noopener noreferrer" onClick={close}><strong>{result.title} ↗</strong><span>{result.description}</span><small>App</small></a> : <button onClick={() => go(result.route, result.kind === "dashboard" ? result.dashboardId : undefined)}><strong>{result.title}</strong><span>{result.description}</span><small>{result.kind === "dashboard" ? "Dashboard" : "Onderdeel"}</small></button>}</li>)}</ul>
      {engines.length > 0 && <><p>Extern zoeken · alleen na je keuze</p><ul>{engines.map(engine => <li key={engine.id}><a href={externalSearchUrl(engine, query)} target="_blank" rel="noopener noreferrer" onClick={close}>Zoek met {engine.name} ↗</a></li>)}</ul></>}
      {engineError && <p role="status">{engineError}</p>}
      <button className="cd-search-manage" onClick={() => { setOpen(false); setManaging(true); }}>Zoekmachines beheren</button>
    </div>}
    <Modal open={managing} title="Zoekmachines beheren" onClose={() => setManaging(false)}>
      {managing && <><SearchEngineManager engines={engines} csrfToken={csrfToken} onChanged={loadEngines} onBack={() => setManaging(false)}/>{engineError && <p role="status">{engineError}</p>}</>}
    </Modal>
  </div>;
}
