"use client";
import {useCallback, useEffect, useRef, useState} from "react";
import {breadcrumbs, downloadUrl, filesPath, filesRequest, FilesRequestError, formatSize, joinPath, MAX_UPLOAD, parentPath, uploadPlan, type FileItem, type FilesConnection} from "../lib/files";
import {useEditMode} from "./edit-mode";
import "./files.css";

type Upload = {id: string; name: string; done: number; total: number; error: string; controller: AbortController};
const SMALL = 32 * 1024 * 1024;

/** Own Nextcloud files from any browser: browse, download, upload (chunked up to 10 GB); edit actions in edit mode. */
export function FilesPage({csrfToken, isAdmin}: {csrfToken: string; isAdmin: boolean}) {
  const editMode = useEditMode();
  const [server, setServer] = useState<{configured: boolean; url: string | null} | null>(null);
  const [connection, setConnection] = useState<FilesConnection | null>(null);
  const [path, setPath] = useState("");
  const [items, setItems] = useState<FileItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [linking, setLinking] = useState(false);
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [serverUrl, setServerUrl] = useState("");
  const [dragging, setDragging] = useState(false);
  const picker = useRef<HTMLInputElement>(null);

  const fail = useCallback((failure: unknown) => {
    if (failure instanceof FilesRequestError && failure.relink) setConnection(value => value ? {...value, linked: false} : value);
    setError(failure instanceof Error ? failure.message : "Files is niet beschikbaar.");
  }, []);
  const loadStatus = useCallback(async () => {
    try {
      const status = await filesRequest<{configured: boolean; url: string | null}>("/server");
      setServer(status);
      if (status.configured) setConnection(await filesRequest<FilesConnection>("/connection"));
    } catch (failure) { fail(failure); }
  }, [fail]);
  const list = useCallback(async (target: string) => {
    setLoading(true); setError("");
    try {
      const result = await filesRequest<{path: string; items: FileItem[]}>(`/list?path=${encodeURIComponent(filesPath(target))}`);
      setItems(result.items); setPath(result.path);
    } catch (failure) { fail(failure); } finally { setLoading(false); }
  }, [fail]);
  useEffect(() => { void loadStatus(); }, [loadStatus]);
  useEffect(() => { if (connection?.linked) void list(""); }, [connection?.linked, list]);

  const link = async () => {
    setError(""); setLinking(true);
    const popup = window.open("about:blank", "_blank");
    try {
      const {loginUrl} = await filesRequest<{loginUrl: string}>("/connection", csrfToken, "POST", {});
      if (popup) popup.location.href = loginUrl; else window.open(loginUrl, "_blank", "noopener");
      const started = Date.now();
      while (Date.now() - started < 20 * 60 * 1000) {
        await new Promise(resolve => setTimeout(resolve, 2000));
        const result = await filesRequest<{state: string}>("/connection/poll", csrfToken, "POST", {});
        if (result.state === "linked") { popup?.close(); await loadStatus(); return; }
      }
      setError("De koppeling is verlopen. Probeer opnieuw.");
    } catch (failure) { popup?.close(); fail(failure); } finally { setLinking(false); }
  };
  const unlink = async () => {
    if (!window.confirm("Koppeling met Nextcloud verwijderen? Het app-wachtwoord wordt ook in Nextcloud ingetrokken.")) return;
    try { setConnection(await filesRequest<FilesConnection>("/connection", csrfToken, "DELETE")); setItems([]); } catch (failure) { fail(failure); }
  };
  const act = async (action: () => Promise<unknown>) => { setError(""); try { await action(); await list(path); } catch (failure) { fail(failure); } };

  const uploadOne = async (file: File) => {
    const id = crypto.randomUUID(), controller = new AbortController();
    const update = (patch: Partial<Upload>) => setUploads(values => values.map(value => value.id === id ? {...value, ...patch} : value));
    setUploads(values => [...values, {id, name: file.name, done: 0, total: file.size, error: "", controller}]);
    let target: string;
    try { target = joinPath(path, file.name); if (file.size > MAX_UPLOAD) throw new RangeError("Een bestand mag hooguit 10 GB zijn."); }
    catch (failure) { update({error: (failure as Error).message}); return; }
    const confirmOverwrite = (failure: unknown) => failure instanceof FilesRequestError && failure.status === 409 && !failure.relink && window.confirm(`‘${file.name}’ bestaat al. Overschrijven?`);
    let upload: string | null = null;
    try {
      if (file.size <= SMALL) {
        const send = (overwrite: boolean) => filesRequest(`/upload?path=${encodeURIComponent(target)}${overwrite ? "&overwrite=1" : ""}`, csrfToken, "PUT", file, controller.signal);
        try { await send(false); } catch (failure) { if (!confirmOverwrite(failure)) throw failure; await send(true); }
      } else {
        const started = await filesRequest<{id: string; chunkSize: number}>("/uploads", csrfToken, "POST", {path: target, size: file.size}, controller.signal);
        upload = started.id;
        for (const part of uploadPlan(file.size, started.chunkSize)) {
          await filesRequest(`/uploads/${upload}/${part.index}?path=${encodeURIComponent(target)}`, csrfToken, "PUT", file.slice(part.start, part.end), controller.signal);
          update({done: part.end});
        }
        const finish = (overwrite: boolean) => filesRequest(`/uploads/${upload}/finish`, csrfToken, "POST", {path: target, size: file.size, overwrite}, controller.signal);
        try { await finish(false); } catch (failure) { if (!confirmOverwrite(failure)) throw failure; await finish(true); }
        upload = null;
      }
      update({done: file.size});
      setUploads(values => values.filter(value => value.id !== id));
      await list(path);
    } catch (failure) {
      if (upload) void filesRequest(`/uploads/${upload}`, csrfToken, "DELETE").catch(() => undefined);
      update({error: controller.signal.aborted ? "Geannuleerd." : failure instanceof Error ? failure.message : "Uploaden mislukt."});
      if (failure instanceof FilesRequestError && failure.relink) fail(failure);
    }
  };
  const uploadAll = (list: FileList | null) => { for (const file of Array.from(list ?? [])) void uploadOne(file); };

  if (!server) return <section className="files-page"><p role="status">{error || "Files laden…"}</p></section>;
  if (!server.configured) return <section className="files-page">
    <p>Files is nog niet ingericht.{isAdmin ? " Vul het adres van je Nextcloud in." : " Vraag je beheerder het Nextcloud-adres in te stellen."}</p>
    {isAdmin && <form className="files-inline" onSubmit={event => { event.preventDefault(); void filesRequest("/server", csrfToken, "PUT", {url: serverUrl}).then(() => loadStatus()).catch(fail); }}>
      <label>Nextcloud-adres<input type="url" required placeholder="https://cloud.example.org" value={serverUrl} onChange={event => setServerUrl(event.target.value)}/></label><button type="submit">Opslaan</button>
    </form>}
    {error && <p role="alert" className="config-error">{error}</p>}
  </section>;
  if (!connection?.linked) return <section className="files-page">
    <p>Koppel je Nextcloud-account om je bestanden hier te openen, ook vanaf een computer zonder Nextcloud-client.</p>
    <p className="files-muted">Je meldt je aan bij Nextcloud en keurt de toegang goed. ControlDeck krijgt een eigen app-wachtwoord dat je in Nextcloud kunt intrekken; het verlaat de ControlDeck-server nooit.</p>
    <button onClick={() => void link()} disabled={linking}>{linking ? "Wachten op Nextcloud… keur de toegang goed in het geopende venster" : "Koppelen met Nextcloud"}</button>
    {error && <p role="alert" className="config-error">{error}</p>}
  </section>;

  const crumbs = breadcrumbs(path);
  return <section className="files-page" onDragOver={event => { if (event.dataTransfer.types.includes("Files")) { event.preventDefault(); setDragging(true); } }}
    onDragLeave={event => { if (event.currentTarget === event.target) setDragging(false); }} onDrop={event => { event.preventDefault(); setDragging(false); uploadAll(event.dataTransfer.files); }} data-dragging={dragging}>
    <div className="files-toolbar">
      <nav aria-label="Map">{crumbs.map((crumb, index) => <span key={crumb.path}>{index > 0 && " / "}{index === crumbs.length - 1 ? <strong>{crumb.name}</strong> : <button className="files-link" onClick={() => void list(crumb.path)}>{crumb.name}</button>}</span>)}</nav>
      <div className="files-actions">
        <button onClick={() => picker.current?.click()}>Uploaden</button>
        <input ref={picker} type="file" multiple hidden onChange={event => { uploadAll(event.target.files); event.target.value = ""; }}/>
        {editMode && <button onClick={() => { const name = window.prompt("Naam van de nieuwe map"); if (name) void act(() => filesRequest("/folder", csrfToken, "POST", {path: joinPath(path, name)})); }}>Nieuwe map</button>}
        <button onClick={() => void list(path)} disabled={loading}>Vernieuwen</button>
        {server.url && <a href={`${server.url}/apps/files/?dir=${encodeURIComponent("/" + path)}`} target="_blank" rel="noopener noreferrer">Open in Nextcloud ↗</a>}
        {editMode && <button onClick={() => void unlink()}>Ontkoppelen</button>}
      </div>
    </div>
    {error && <p role="alert" className="config-error">{error}</p>}
    {uploads.length > 0 && <ul className="files-uploads">{uploads.map(upload => <li key={upload.id}>
      <span>{upload.name}</span><progress max={upload.total || 1} value={upload.done}/>{upload.error ? <><span className="config-error">{upload.error}</span><button onClick={() => setUploads(values => values.filter(value => value.id !== upload.id))}>Sluiten</button></> : <button onClick={() => upload.controller.abort()}>Annuleren</button>}
    </li>)}</ul>}
    <table className="files-table">
      <thead><tr><th>Naam</th><th>Grootte</th><th>Gewijzigd</th>{editMode && <th><span className="sr-only">Acties</span></th>}</tr></thead>
      <tbody>
        {path && <tr><td colSpan={editMode ? 4 : 3}><button className="files-link" onClick={() => void list(parentPath(path))}>↰ Bovenliggende map</button></td></tr>}
        {items.map(item => { const full = joinPath(path, item.name); return <tr key={item.name}>
          <td>{item.type === "folder" ? <button className="files-link" onClick={() => void list(full)}>📁 {item.name}</button> : <a href={downloadUrl(full)} download>📄 {item.name}</a>}</td>
          <td>{formatSize(item.size)}</td>
          <td>{item.modified ? new Date(item.modified * 1000).toLocaleString("nl-NL", {dateStyle: "short", timeStyle: "short"}) : ""}</td>
          {editMode && <td className="files-row-actions">
            <button onClick={() => { const name = window.prompt("Nieuwe naam", item.name); if (name && name !== item.name) void act(() => filesRequest("/move", csrfToken, "POST", {from: full, to: joinPath(path, name)})); }}>Hernoemen</button>
            <button onClick={() => { const folder = window.prompt("Verplaatsen naar map (leeg = hoofdmap)", path); if (folder !== null) void act(() => filesRequest("/move", csrfToken, "POST", {from: full, to: joinPath(filesPath(folder), item.name)})); }}>Verplaatsen</button>
            <button onClick={() => { if (window.confirm(`‘${item.name}’ verwijderen? Het gaat naar de prullenbak van Nextcloud.`)) void act(() => filesRequest(`/item?path=${encodeURIComponent(full)}`, csrfToken, "DELETE")); }}>Verwijderen</button>
          </td>}
        </tr>; })}
        {!loading && !items.length && <tr><td colSpan={editMode ? 4 : 3} className="files-muted">Deze map is leeg. Sleep bestanden hierheen of kies Uploaden.</td></tr>}
      </tbody>
    </table>
    {loading && <p role="status">Laden…</p>}
  </section>;
}
