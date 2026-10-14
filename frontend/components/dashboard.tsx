"use client";

import {useCallback, useEffect, useRef, useState, type CSSProperties} from "react";
import {dashboardRequest, firstSpace, placeItem, removeSection, configureItem, dashboardItemView, filterDashboardApps, type Dashboard, type DashboardItem, type DashboardList, type DashboardSection, type DashboardApps} from "../lib/dashboards";
import {AppIcon, AppIconPicker} from "./app-icon";
import {DashboardModule, LinkwardenCollectionPicker} from "./dashboard-module";
import {moduleOptions} from "../lib/dashboard-modules";
import {Modal} from "./modal";
import "./dashboard.css";

type Dialog = {kind: "picker"} | {kind: "create" | "duplicate"; title: string} | {kind: "item"; item: DashboardItem} | {kind: "section"; section: DashboardSection} | {kind: "apps"; appId: number | null; sectionId: string; query: string} | null;
const lanes = [{id: "left", title: "Linkerpaneel"}, {id: "main", title: "Midden"}, {id: "right", title: "Rechterpaneel"}] as const;

export function DashboardPage({csrfToken, onEditingChange, sourceAccess, selection}: {csrfToken: string; onEditingChange: (editing: boolean) => void; sourceAccess: boolean; selection?: {id: string; token: number} | null}) {
  const [boards, setBoards] = useState<Dashboard[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [defaultId, setDefaultId] = useState<string | null>(null);
  const [draft, setDraft] = useState<Dashboard | null>(null);
  const [dialog, setDialog] = useState<Dialog>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [sources, setSources] = useState<DashboardApps>({apps: [], available: false, warning: null});
  const [sourceLoading, setSourceLoading] = useState(false);
  const authorizedApps = sourceAccess ? sources.apps : [];
  const resize = useRef<{board: Dashboard; item: DashboardItem; x: number; y: number; pitch: number} | null>(null);
  const board = draft ?? boards.find(value => value.id === activeId) ?? null;
  const editing = !!draft;
  useEffect(() => { onEditingChange(editing); return () => onEditingChange(false); }, [editing, onEditingChange]);
  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true); setError("");
    try {
      const result = await dashboardRequest<DashboardList>("", "", "GET", undefined, signal);
      if (signal?.aborted) return;
      setBoards(result.dashboards); setDefaultId(result.defaultId);
      setActiveId(current => result.dashboards.some(value => value.id === current) ? current : result.defaultId ?? result.dashboards[0]?.id ?? null);
    } catch (failure) { if (!signal?.aborted) setError(failure instanceof Error ? failure.message : "Laden mislukt."); }
    finally { if (!signal?.aborted) setLoading(false); }
  }, []);
  useEffect(() => { const controller = new AbortController(); void load(controller.signal); return () => controller.abort(); }, [load]);
  const loadSources = useCallback(async (signal?: AbortSignal) => {
    setSourceLoading(true);
    try {
      const value = await dashboardRequest<DashboardApps>("/apps", "", "GET", undefined, signal);
      if (!signal?.aborted) setSources(value);
    } catch { if (!signal?.aborted) setSources({apps: [], available: false, warning: "App-lijst niet beschikbaar. Je eigen links blijven bruikbaar."}); }
    finally { if (!signal?.aborted) setSourceLoading(false); }
  }, []);
  useEffect(() => { const controller = new AbortController(); if (sourceAccess) void loadSources(controller.signal); else setSources({apps: [], available: false, warning: null}); return () => controller.abort(); }, [loadSources, sourceAccess]);
  const handledRequest = useRef<number | null>(null);
  useEffect(() => {
    if (!selection || loading || handledRequest.current === selection.token) return;
    const requestedId = selection.id;
    handledRequest.current = selection.token;
    if (!boards.some(value => value.id === requestedId)) {setError("Het gekozen dashboard is niet beschikbaar."); return;}
    if (draft && draft.id !== requestedId && !window.confirm("Je dashboardbewerking verwerpen en het zoekresultaat openen?")) return;
    if (!draft || draft.id !== requestedId) {setDraft(null); setActiveId(requestedId); setError("");}
  }, [selection, loading, boards, draft]);
  useEffect(() => {
    if (!draft) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [draft]);

  const perform = async (action: () => Promise<void>) => {
    setBusy(true); setError(""); setNotice("");
    try { await action(); } catch (failure) { setError(failure instanceof Error ? failure.message : "Opslaan mislukt."); }
    finally { setBusy(false); }
  };
  const change = (action: (value: Dashboard) => Dashboard) => {
    if (!draft) return;
    try { setDraft(action(draft)); setError(""); } catch (failure) { setError(failure instanceof Error ? failure.message : "Aanpassen mislukt."); }
  };
  const save = () => perform(async () => {
    if (!draft) return;
    const {id, ...body} = draft;
    const result = await dashboardRequest<{dashboard: Dashboard}>(`/${id}`, csrfToken, "PUT", body);
    setBoards(values => values.map(value => value.id === id ? result.dashboard : value)); setDraft(null); setNotice("Dashboard opgeslagen.");
  });
  const addItem = () => {
    if (!draft) return;
    try {
      const sectionId = draft.sections.find(section => section.lane === "main")?.id ?? draft.sections[0].id;
      setDialog({kind: "item", item: {id: crypto.randomUUID(), type: "link", sectionId, title: "", url: "", description: "", width: 4, height: 1, ...firstSpace(draft, sectionId)}});
    } catch (failure) { setError((failure as Error).message); }
  };
  const submitDialog = () => {
    if (!dialog) return;
    if (dialog.kind === "create" || dialog.kind === "duplicate") {
      void perform(async () => {
        const result = await dashboardRequest<{dashboard: Dashboard}>("", csrfToken, "POST", {title: dialog.title, ...(dialog.kind === "duplicate" ? {sourceId: activeId} : {})});
        setBoards(values => [...values, result.dashboard]); setActiveId(result.dashboard.id); setDialog(null);
      });
    } else if (dialog.kind === "item" && draft) {
      try {
        setDraft(configureItem(draft, dialog.item)); setDialog(null); setError("");
      } catch (failure) { setError((failure as Error).message); }
    } else if (dialog.kind === "apps" && draft) {
      try {
        if (!authorizedApps.some(app => app.id === dialog.appId)) throw new Error("Kies een beschikbare app.");
        const width = draft.sections.find(section => section.id === dialog.sectionId)?.lane === "main" ? 4 : 12;
        const item: DashboardItem = {id: crypto.randomUUID(), type: "app", appId: dialog.appId!, sectionId: dialog.sectionId, width, height: 2, ...firstSpace(draft, dialog.sectionId, width, 2)};
        setDraft(placeItem(draft, item)); setDialog(null); setError("");
      } catch (failure) {setError((failure as Error).message);}
    } else if (dialog.kind === "section" && draft) {
      const existing = draft.sections.some(section => section.id === dialog.section.id);
      if (!existing && draft.sections.length >= 20) { setError("Maximaal 20 groepen."); return; }
      setDraft({...draft, sections: existing ? draft.sections.map(section => section.id === dialog.section.id ? dialog.section : section) : [...draft.sections, dialog.section]});
      setDialog(null); setError("");
    }
  };

  return <section className="cd-dashboard" aria-label="Persoonlijk dashboard">
    <div className="cd-dashboard-toolbar">
      <label>Dashboard<select disabled={busy || !!draft || loading} value={activeId ?? ""} onChange={event => {setActiveId(event.target.value); setError(""); setNotice("");}}>
        {!boards.length && <option value="">Geen dashboards</option>}{boards.map(value => <option key={value.id} value={value.id}>{value.title}{value.id === defaultId ? " · standaard" : ""}</option>)}
      </select></label>
      <div className="cd-dashboard-actions">
        {draft ? <><button disabled={busy} onClick={() => setDialog({kind: "picker"})}>Module toevoegen</button><button disabled={busy || draft.sections.length >= 20} onClick={() => setDialog({kind: "section", section: {id: crypto.randomUUID(), title: "", lane: "main", collapsed: false}})}>Groep toevoegen</button><button className="cd-dashboard-primary" disabled={busy} onClick={() => void save()}>{busy ? "Opslaan…" : "Opslaan"}</button><button disabled={busy} onClick={() => {if (window.confirm("Bewerkingen verwerpen?")) {setDraft(null); setError("");}}}>Annuleren</button></> : <>
          <button disabled={busy || loading || boards.length >= 20} onClick={() => setDialog({kind: "create", title: ""})}>Nieuw dashboard</button>
          {board && <><button disabled={busy || loading} onClick={() => {setDraft(structuredClone(board)); setError(""); setNotice("");}}>Bewerken</button><button disabled={busy || boards.length >= 20} onClick={() => setDialog({kind: "duplicate", title: `${board.title} kopie`.slice(0,100)})}>Dupliceren</button><button disabled={busy || defaultId === board.id} onClick={() => void perform(async () => {await dashboardRequest("/default", csrfToken, "PUT", {id: board.id}); setDefaultId(board.id); setNotice("Standaarddashboard ingesteld.");})}>Als standaard</button></>}
        </>}
      </div>
    </div>
    {error && <div role="alert" className="config-error">{error} <button disabled={busy} onClick={() => {if (!draft || window.confirm("Je bewerking verwerpen en de opgeslagen versie herladen?")) {setDraft(null); setDialog(null); void load();}}}>Opgeslagen versie herladen</button></div>}
    <p role="status" className="cd-dashboard-status">{notice || (loading ? "Dashboards laden…" : draft ? "Bewerkmodus · wijzigingen worden pas bewaard met Opslaan." : "")}</p>
    {sourceAccess && <div className="cd-dashboard-source-status">{draft&&<button disabled={sourceLoading} onClick={() => void loadSources()}>App-lijst vernieuwen</button>}{sources.warning && <p role="status">{sources.warning}</p>}</div>}
    {!loading && !board && !error && <p>Maak een dashboard aan om je toepassingen bij elkaar te zetten.</p>}
    {board && <div inert={busy}>
      <div className="cd-dashboard-heading">{draft ? <label>Dashboardnaam<input maxLength={100} required value={draft.title} onChange={event => setDraft({...draft, title: event.target.value})}/></label> : <h3>{board.title}</h3>}
        {!draft && <button disabled={busy} onClick={() => {if (window.confirm(`Dashboard ‘${board.title}’ verwijderen? De apps zelf blijven bestaan.`)) void perform(async () => {await dashboardRequest(`/${board.id}`, csrfToken, "DELETE", {revision: board.revision}); setBoards(values => values.filter(value => value.id !== board.id)); setActiveId(null); await load();});}}>Dashboard verwijderen</button>}
      </div>
      <div className="cd-dashboard-lanes" data-left={board.sections.some(section => section.lane === "left")} data-right={board.sections.some(section => section.lane === "right")}>
        {lanes.map(lane => <div key={lane.id} className={`cd-dashboard-lane cd-dashboard-lane-${lane.id}`} aria-label={lane.title}>
          {board.sections.filter(section => section.lane === lane.id).map(section => <section key={section.id} className="cd-dashboard-group">
            <div className="cd-dashboard-group-heading"><button aria-expanded={!section.collapsed} onClick={() => {
              if (draft) change(value => ({...value, sections: value.sections.map(s => s.id === section.id ? {...s, collapsed: !s.collapsed} : s)}));
              else setBoards(values => values.map(value => value.id === board.id ? {...value, sections: value.sections.map(s => s.id === section.id ? {...s, collapsed: !s.collapsed} : s)} : value));
            }}>{section.collapsed ? "▸" : "▾"} {section.title}</button>{draft && <button onClick={() => setDialog({kind: "section", section})} aria-label={`Groep ${section.title} aanpassen`}>Aanpassen</button>}</div>
            {(!section.collapsed || draft) && <div className="cd-dashboard-grid" data-editing={!!draft} style={{"--dashboard-rows": Math.max(draft ? 3 : 1, ...board.items.filter(item => item.sectionId === section.id).map(item => item.y + item.height))} as CSSProperties}
              onDragOver={event => {if (draft && event.dataTransfer.types.includes("application/x-controldeck-item")) event.preventDefault();}}
              onDrop={event => {
                if (!draft) return; event.preventDefault();
                const item = draft.items.find(value => value.id === event.dataTransfer.getData("application/x-controldeck-item")); if (!item) return;
                const rect = event.currentTarget.getBoundingClientRect();
                change(value => placeItem(value, {...item, sectionId: section.id, x: Math.min(12 - item.width, Math.max(0, Math.floor((event.clientX - rect.left) / ((rect.width + 12) / 12)))), y: Math.min(100 - item.height, Math.max(0, Math.floor((event.clientY - rect.top) / 84)))}));
              }}>
              {board.items.filter(item => item.sectionId === section.id).map(item => {
                const view = dashboardItemView(item, authorizedApps);
                return <article key={item.id} className={`cd-dashboard-tile${item.type === "module" ? " cd-dashboard-module-tile" : ""}`} style={{gridColumn: `${item.x + 1} / span ${item.width}`, gridRow: `${item.y + 1} / span ${item.height}`}}>
                {draft ? <><div className="cd-dashboard-tile-controls"><button draggable aria-label={`${view.title} verplaatsen`} title="Sleep naar een vrije plaats" onDragStart={event => {event.dataTransfer.setData("application/x-controldeck-item", item.id); event.dataTransfer.effectAllowed = "move";}}>⠿</button><button onClick={() => setDialog({kind: "item", item})}>Aanpassen</button></div><strong>{view.title}</strong></> : item.type === "module" ? <DashboardModule moduleId={item.moduleId} collectionId={item.settings.collectionId} csrfToken={csrfToken} allowed={sourceAccess}/> : view.url ? <a href={view.url} target="_blank" rel="noopener noreferrer"><AppIcon key={`${view.url}:${item.icon || view.icon}`} name={view.title} url={view.url} icon={item.icon || view.icon}/><strong>{view.title}</strong>{view.description && <span>{view.description}</span>}{view.summary.length > 0 && <><span>{view.summary.map(stat => `${stat.label}: ${stat.value}`).join(" · ")}</span><small>Laatst opgeslagen cijfers</small></>}<small>{new URL(view.url).hostname} ↗</small></a> : <div className="cd-dashboard-unavailable"><strong>{view.title}</strong><span>{view.description}</span></div>}
                {draft && <button className="cd-dashboard-resize" aria-label={`${view.title} vergroten of verkleinen`} title="Sleep voor formaat; pijltjestoetsen werken ook"
                  onPointerDown={event => {const grid = event.currentTarget.closest(".cd-dashboard-grid"); if (!grid) return; resize.current = {board: draft, item, x: event.clientX, y: event.clientY, pitch: (grid.getBoundingClientRect().width + 12) / 12}; event.currentTarget.setPointerCapture(event.pointerId);}}
                  onPointerMove={event => {const start = resize.current; if (!start) return; try {setDraft(placeItem(start.board, {...start.item, width: Math.max(1, Math.min(12 - start.item.x, start.item.width + Math.round((event.clientX - start.x) / start.pitch))), height: Math.max(1, Math.min(6, start.item.height + Math.round((event.clientY - start.y) / 84)))}));} catch {/* Keep the last valid size on collision. */}}}
                  onPointerUp={() => {resize.current = null;}} onPointerCancel={() => {if (resize.current) setDraft(resize.current.board); resize.current = null;}}
                  onKeyDown={event => {const delta = {ArrowLeft: [-1,0], ArrowRight: [1,0], ArrowUp: [0,-1], ArrowDown: [0,1]}[event.key]; if (delta) {event.preventDefault(); change(value => placeItem(value, {...item, width: item.width + delta[0], height: item.height + delta[1]}));}}}>↘</button>}
              </article>;})}
              {!board.items.some(item => item.sectionId === section.id) && <p className="cd-dashboard-empty">{draft ? "Voeg een module toe of sleep hier een tegel naartoe." : "Deze groep is nog leeg. Kies Bewerken om modules toe te voegen."}</p>}
            </div>}
          </section>)}
        </div>)}
      </div>
    </div>}
    <Modal open={!!dialog} title={dialog?.kind === "picker" ? "Module toevoegen" : dialog?.kind === "apps" ? "Bestaande app toevoegen" : dialog?.kind === "item" ? dialog.item.type === "module" ? "Module instellen" : "App-link aanpassen" : dialog?.kind === "section" ? "Groep aanpassen" : dialog?.kind === "duplicate" ? "Dashboard dupliceren" : "Nieuw dashboard"} onClose={() => {if (!busy) setDialog(null);}}>
      {dialog && <form className="cd-dashboard-form" onSubmit={event => {event.preventDefault(); submitDialog();}}>
        {dialog.kind === "picker" && <div className="cd-module-picker">
          <p>Kies wat je op dit dashboard wilt zien. Je bestaande koppelingen worden gebruikt.</p>
          {moduleOptions(sourceAccess ? ["bookmarks"] : []).map(module => <button key={module.id} type="button" onClick={() => {
            if (!draft) return;
            try {const sectionId=draft.sections.find(section=>section.lane==="main")?.id ?? draft.sections[0].id; setDialog({kind:"item",item:{id:crypto.randomUUID(),type:"module",moduleId:module.id,settings:{collectionId:null},sectionId,width:module.width,height:module.height,...firstSpace(draft,sectionId,module.width,module.height)}});} catch(failure) {setError((failure as Error).message);}
          }}><strong>{module.title}</strong><span>{module.description}</span></button>)}
          {sourceAccess&&<button type="button" onClick={()=>setDialog({kind:"apps",appId:null,sectionId:draft!.sections[0].id,query:""})}><strong>Apps</strong><span>Kies een bestaande app uit Bookmarks</span></button>}
          <button type="button" onClick={addItem}><strong>Persoonlijke link</strong><span>Een eigen snelkoppeling naar een website</span></button>
        </div>}
        {(dialog.kind === "create" || dialog.kind === "duplicate") && <label>Naam<input autoFocus required maxLength={100} value={dialog.title} onChange={event => setDialog({...dialog, title: event.target.value})}/></label>}
        {dialog.kind === "apps" && <>
          <p>Kies een bestaande Homepage-app. Naam, adres, icoon en opgeslagen integratiecijfers volgen de bron in Bookmarks.</p>
          <label>Apps zoeken<input type="search" maxLength={200} value={dialog.query} onChange={event => setDialog({...dialog, query: event.target.value, appId: null})}/></label>
          <label>App<select required value={dialog.appId ?? ""} onChange={event => setDialog({...dialog, appId: Number(event.target.value) || null})}><option value="">Kies een app</option>{filterDashboardApps(authorizedApps, dialog.query).map(app => <option key={app.id} value={app.id}>{app.name} · {app.collection}</option>)}</select></label>
          {!filterDashboardApps(authorizedApps, dialog.query).length && <p>Geen apps gevonden. Voeg een app toe in Bookmarks of vernieuw de app-lijst.</p>}
          <label>Groep<select value={dialog.sectionId} onChange={event => setDialog({...dialog, sectionId: event.target.value})}>{draft?.sections.map(section => <option key={section.id} value={section.id}>{section.title}</option>)}</select></label>
        </>}
        {dialog.kind === "section" && <><label>Groepsnaam<input autoFocus required maxLength={100} value={dialog.section.title} onChange={event => setDialog({...dialog, section: {...dialog.section, title: event.target.value}})}/></label><label>Plaats<select value={dialog.section.lane} onChange={event => setDialog({...dialog, section: {...dialog.section, lane: event.target.value as DashboardSection["lane"]}})}>{lanes.map(lane => <option key={lane.id} value={lane.id}>{lane.title}</option>)}</select></label><label><input type="checkbox" checked={dialog.section.collapsed} onChange={event => setDialog({...dialog, section: {...dialog.section, collapsed: event.target.checked}})}/>Ingeklapt starten</label><button type="button" onClick={() => {try {if (draft) setDraft(removeSection(draft, dialog.section.id)); setDialog(null);} catch (failure) {setError((failure as Error).message);}}}>Lege groep verwijderen</button></>}
        {dialog.kind === "item" && <>
          {dialog.item.type === "link" ? <AppIconPicker value={dialog.item.icon || ""} onBusy={setBusy} onChange={icon => setDialog(current => {if(current?.kind !== "item") return current; const {icon: previous, ...item} = current.item; return {...current, item: icon ? {...item, icon} : item};})}/> : dialog.item.type === "app" ? <p>Naam, adres en icoon beheer je bij <a href="#bookmarks">Bookmarks</a>. Hier pas je de plaatsing aan.</p> : <><p>Deze module gebruikt je bestaande persoonlijke Linkwarden-koppeling.</p>{sourceAccess ? <LinkwardenCollectionPicker value={dialog.item.settings.collectionId} csrfToken={csrfToken} onChange={collectionId=>setDialog(current=>current?.kind==="item"&&current.item.type==="module"?{...current,item:{...current.item,settings:{collectionId}}}:current)}/> : <p>Je hebt geen toegang tot Linkwarden. Je kunt de module verplaatsen of verwijderen.</p>}</>}
          {dialog.item.type === "app" ? <p>Gekoppelde app: {dashboardItemView(dialog.item, authorizedApps).title}. Pas de bron aan in Bookmarks.</p> : dialog.item.type === "link" ? ([['title','Naam',300],['url','Adres',2048],['description','Beschrijving',1000]] as const).map(([key,label,max]) => <label key={key}>{label}<input autoFocus={key === "title"} type={key === "url" ? "url" : "text"} required={key !== "description"} maxLength={max} value={dialog.item.type === "link" ? dialog.item[key] : ""} onChange={event => {if (dialog.item.type === "link") setDialog({...dialog, item: {...dialog.item, [key]: event.target.value}});}}/></label>) : null}
          <label>Groep<select value={dialog.item.sectionId} onChange={event => setDialog({...dialog, item: {...dialog.item, sectionId: event.target.value}})}>{draft?.sections.map(section => <option key={section.id} value={section.id}>{section.title}</option>)}</select></label>
          <details className="cd-dashboard-placement"><summary>Plaats en grootte</summary><div className="cd-dashboard-coordinates">{([['x','Kolom (vanaf 0)',0,11],['y','Rij (vanaf 0)',0,99],['width','Breedte',1,12],['height','Hoogte',1,6]] as const).map(([key,label,min,max]) => <label key={key}>{label}<input type="number" required min={min} max={max} value={dialog.item[key]} onChange={event => setDialog({...dialog, item: {...dialog.item, [key]: Number(event.target.value)}})}/></label>)}</div></details>
          {draft?.items.some(item=>item.id===dialog.item.id)&&<button type="button" onClick={() => {if (draft) setDraft({...draft, items: draft.items.filter(item => item.id !== dialog.item.id)}); setDialog(null);}}>Verwijderen uit dashboard</button>}
        </>}
        {error && <p role="alert">{error}</p>}
        <div className="cd-dashboard-actions">{dialog.kind !== "picker" && <button disabled={busy} type="submit">{busy ? "Bezig…" : dialog.kind === "create" || dialog.kind === "duplicate" ? "Aanmaken" : "Toepassen"}</button>}<button disabled={busy} type="button" onClick={() => setDialog(null)}>Annuleren</button></div>
      </form>}
    </Modal>
  </section>;
}
