"use client";
import {useCallback, useEffect, useState} from "react";
import {connectLink, validateOverview, virtualAppsRequest, VirtualAppsError, type VirtualOverview} from "../lib/virtual-apps";
import "./virtual-apps.css";

/** All Kasm workspaces the user may start; a click starts one in a new tab. Running sessions can be stopped. */
export function VirtualAppsPage({csrfToken}: {csrfToken: string}) {
  const [data, setData] = useState<VirtualOverview | null>(null);
  const [error, setError] = useState<VirtualAppsError | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const load = useCallback(async () => {
    try { setData(validateOverview(await virtualAppsRequest("", "", "GET"))); setError(null); }
    catch (failure) { setError(failure instanceof VirtualAppsError ? failure : new VirtualAppsError("Virtual Apps is niet beschikbaar.")); }
  }, []);
  useEffect(() => { void load(); const timer = setInterval(() => void load(), 30000); return () => clearInterval(timer); }, [load]);
  const start = async (id: string) => {
    if (!data) return;
    // Open the tab within the click so pop-up blockers allow it; navigate once Kasm returns the link.
    const tab = window.open("about:blank", "_blank");
    setBusy(id); setError(null);
    try {
      const {url} = await virtualAppsRequest<{url: string}>(`/${id}/start`, csrfToken, "POST");
      const link = connectLink(url, data.portal);
      if (tab) { tab.opener = null; tab.location.href = link; } else window.open(link, "_blank", "noopener");
      await load();
    } catch (failure) { tab?.close(); setError(failure instanceof VirtualAppsError ? failure : new VirtualAppsError("Starten mislukt.")); }
    finally { setBusy(null); }
  };
  const stop = async (id: string, name: string) => {
    if (!window.confirm(`Sessie ‘${name}’ stoppen? Niet-opgeslagen werk in die workspace gaat verloren.`)) return;
    setBusy(id);
    try { await virtualAppsRequest(`/sessions/${id}`, csrfToken, "DELETE"); await load(); }
    catch (failure) { setError(failure instanceof VirtualAppsError ? failure : new VirtualAppsError("Stoppen mislukt.")); }
    finally { setBusy(null); }
  };
  if (!data) return <section className="cd-vapps">{error ? <p role="alert" className="config-error">{error.message}</p> : <p role="status">Virtual Apps laden…</p>}</section>;
  const words = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const apps = data.apps.filter(app => words.every(word => `${app.name} ${app.description} ${app.categories.join(" ")}`.toLowerCase().includes(word)));
  return <section className="cd-vapps" aria-label="Virtual Apps">
    <div className="cd-vapps-toolbar">
      <input type="search" aria-label="Zoek een app" placeholder="Zoek een app" maxLength={100} value={query} onChange={event => setQuery(event.target.value)}/>
      <button onClick={() => void load()}>Vernieuwen</button>
      <a href={data.portal} target="_blank" rel="noopener noreferrer">Kasm openen ↗</a>
    </div>
    {error && <p role="alert" className="config-error">{error.message}</p>}
    {data.sessions.length > 0 && <section aria-label="Lopende sessies" className="cd-vapps-sessions"><h3>Lopende sessies</h3><ul>
      {data.sessions.map(session => { const app = data.apps.find(item => item.id === session.appId); return <li key={session.id}>
        {app?.icon ? <img src={app.icon} alt="" loading="lazy" referrerPolicy="no-referrer"/> : <span className="cd-vapps-letter" aria-hidden="true">{session.name.slice(0, 1)}</span>}
        <span><strong>{session.name}</strong><small>{[session.status, session.started && `gestart ${session.started}`].filter(Boolean).join(" · ")}</small></span>
        {session.appId && <button disabled={busy !== null} onClick={() => void start(session.appId!)}>Openen</button>}
        <button disabled={busy !== null} onClick={() => void stop(session.id, session.name)}>{busy === session.id ? "Stoppen…" : "Stoppen"}</button>
      </li>; })}
    </ul></section>}
    {!apps.length ? <p>{data.apps.length ? "Geen apps gevonden." : "Er zijn nog geen workspaces in Kasm beschikbaar."}</p> :
      <ul className="cd-vapps-grid">{apps.map(app => <li key={app.id}>
        <button className="cd-vapps-tile" disabled={busy !== null} onClick={() => void start(app.id)} title={app.description || `${app.name} starten`}>
          {app.icon ? <img src={app.icon} alt="" loading="lazy" referrerPolicy="no-referrer" onError={event => { event.currentTarget.hidden = true; }}/> : <span className="cd-vapps-letter" aria-hidden="true">{app.name.slice(0, 1)}</span>}
          <strong>{app.name}</strong>
          <small>{busy === app.id ? "Starten…" : app.categories[0] ?? ""}</small>
        </button>
      </li>)}</ul>}
  </section>;
}
