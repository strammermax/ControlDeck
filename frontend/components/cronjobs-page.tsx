"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Modal } from "./modal";
import { DAY_LABELS, buildCron, describeCron, isMissed, nextRuns, pickerFor, type Picker } from "../lib/cron";
import { SOURCE_LABELS, runStatus, suggestJobId, summarizeRuns, type CronRun } from "../lib/cronjobs";
import { duration } from "../lib/proxmox";

type Job = { id: string; description: string; schedule: string; user: string; command?: string; enabled: boolean; logs: boolean; timeoutMinutes: number | null; createdAt: number; adopted: boolean; adoptedFrom: string | null; lastRun: CronRun | null };
type SystemEntry = { ref: string; source: string; schedule: string; user: string; command?: string };
type Timer = { unit: string; activates: string; next: number | null; last: number | null };
type NodeData = { node: string; jobs: Job[]; system: SystemEntry[]; timers: Timer[] };
type Props = { isAdmin: boolean; csrfToken: string; refreshSeconds: number };

const time = (seconds: number | null | undefined) => seconds ? new Date(seconds * 1000).toLocaleString("nl-NL", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "—";

async function api<T>(path: string, csrfToken: string, method = "GET", body?: unknown): Promise<T> {
  const response = await fetch(`/api/cronjobs${path}`, { cache: "no-store", method, headers: method === "GET" ? undefined : { "Content-Type": "application/json", "X-CSRF-Token": csrfToken }, body: body === undefined ? undefined : JSON.stringify(body) });
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(typeof data?.error === "string" ? data.error : "Niet beschikbaar.");
  return data;
}

/** Proxmox → Nodes: cluster-wide job history plus a cronjob manager per node (module Cronjobs). */
export function CronjobsPage({ isAdmin, csrfToken, refreshSeconds }: Props) {
  const [nodes, setNodes] = useState<string[] | null>(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("cluster");
  useEffect(() => {
    api<{ nodes: string[] }>("/nodes", csrfToken).then(data => { setNodes(data.nodes); setError(""); }).catch(failure => setError(failure.message));
  }, [csrfToken]);
  if (error) return <div className="proxmox-empty"><p role="alert">{error}</p>{isAdmin && <a className="provider-open" href="#admin/modules">Module Cronjobs in Modulebeheer</a>}</div>;
  if (!nodes) return <p role="status">Laden…</p>;
  if (!nodes.length) return <div className="proxmox-empty"><p>Nog geen nodes gekoppeld voor Cronjobs.</p>{isAdmin ? <a className="provider-open" href="#admin/modules">Koppel nodes via Admin → Modulebeheer → Cronjobs</a> : <p>Vraag een beheerder om de module Cronjobs in te richten.</p>}</div>;
  return <section className="cronjobs">
    <h3>Cronjobs</h3>
    <div className="manage-tabs" role="tablist" aria-label="Cronjobs">
      {["cluster", ...nodes].map(name => <button key={name} role="tab" aria-selected={tab === name} className={tab === name ? "active" : undefined} onClick={() => setTab(name)}>{name === "cluster" ? "Hele cluster" : name}</button>)}
    </div>
    {tab === "cluster" ? <ClusterRuns nodes={nodes} isAdmin={isAdmin} csrfToken={csrfToken} refreshSeconds={refreshSeconds}/> : <NodeJobs key={tab} node={tab} isAdmin={isAdmin} csrfToken={csrfToken}/>}
    <p className="health-ok">Tijden in de tijdzone van je browser.</p>
  </section>;
}

function ClusterRuns({ nodes, isAdmin, csrfToken, refreshSeconds }: { nodes: string[] } & Props) {
  const [hours, setHours] = useState(24);
  const [data, setData] = useState<{ runs: CronRun[]; unavailable: { node: string; error: string }[]; proxmox: boolean } | null>(null);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState({ node: "", status: "", source: "" });
  const [log, setLog] = useState<{ node: string; jobId: string; runId: string } | null>(null);
  const load = useCallback(() => api<typeof data & object>(`/runs?hours=${hours}`, csrfToken).then(value => { setData(value); setError(""); }).catch(failure => setError(failure.message)), [hours, csrfToken]);
  useEffect(() => { void load(); const timer = setInterval(() => void load(), Math.max(15, refreshSeconds) * 1000); return () => clearInterval(timer); }, [load, refreshSeconds]);
  const runs = useMemo(() => (data?.runs ?? []).filter(run => (!filter.node || run.node === filter.node) && (!filter.status || run.status === filter.status) && (!filter.source || run.source === filter.source)), [data, filter]);
  const counts = summarizeRuns(data?.runs ?? []);
  return <>
    <div className="task-toolbar">
      <p className="cron-counts"><strong>Laatste {hours} uur:</strong> {counts.total} runs · <span className="count ok">✓ {counts.ok} OK</span> · <span className={counts.failed ? "count error" : "count none"}>✗ {counts.failed} fout</span> · ◌ {counts.running} bezig · ▷ {counts.started} gestart</p>
      <label>Periode<select value={hours} onChange={event => setHours(Number(event.target.value))}><option value={24}>24 uur</option><option value={72}>3 dagen</option><option value={168}>7 dagen</option><option value={336}>14 dagen</option></select></label>
      <label>Node<select value={filter.node} onChange={event => setFilter({ ...filter, node: event.target.value })}><option value="">Alle</option>{nodes.map(node => <option key={node}>{node}</option>)}</select></label>
      <label>Resultaat<select value={filter.status} onChange={event => setFilter({ ...filter, status: event.target.value })}><option value="">Alle</option><option value="failed">Fout</option><option value="succeeded">OK</option><option value="running">Bezig</option><option value="started">Gestart</option></select></label>
      <label>Bron<select value={filter.source} onChange={event => setFilter({ ...filter, source: event.target.value })}><option value="">Alle</option>{Object.entries(SOURCE_LABELS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
    </div>
    {error && <p className="config-error" role="alert">{error}</p>}
    {data?.unavailable.map(item => <p key={item.node} className="config-error" role="alert">✗ {item.node}: {item.error} De runs van deze node ontbreken.</p>)}
    {!data ? <p role="status">Laden…</p> : runs.length === 0 ? <p>Geen runs in deze periode{filter.node || filter.status || filter.source ? " voor dit filter" : ""}.</p> :
      <div className="task-table"><table>
        <thead><tr><th>Resultaat</th><th>Start</th><th>Duur</th><th>Node</th><th>Job</th><th>Bron</th>{isAdmin && <th>Log</th>}</tr></thead>
        <tbody>{runs.map((run, index) => { const status = runStatus(run); return <tr key={`${run.node}-${run.runId ?? run.start}-${index}`} className={status.level === "error" ? "task-error" : undefined}>
          <td><span className={`task-status ${status.level === "ok" ? "ok" : status.level === "error" ? "error" : status.level === "warning" ? "warning" : ""}`}>{status.label}</span></td>
          <td>{time(run.start)}</td><td>{run.duration != null ? duration(0, run.duration, 0) : "—"}</td><td>{run.node}</td>
          <td>{run.jobId ?? (isAdmin ? <code>{run.command}</code> : "—")}{run.description ? <span className="muted"> · {run.description}</span> : null}{run.message ? <div className="task-message">{run.message}</div> : null}</td>
          <td>{SOURCE_LABELS[run.source] ?? run.source}</td>
          {isAdmin && <td>{run.source === "controldeck" && run.jobId && run.runId ? <button type="button" className="task-more" onClick={() => setLog({ node: run.node, jobId: run.jobId!, runId: run.runId! })}>bekijken</button> : "—"}</td>}
        </tr>; })}</tbody></table></div>}
    {data && !data.proxmox && <p className="health-ok">Proxmox-backups ontbreken: Proxmox VE is niet gekoppeld of niet bereikbaar.</p>}
    {log && <LogModal {...log} csrfToken={csrfToken} onClose={() => setLog(null)}/>}
  </>;
}

function NodeJobs({ node, isAdmin, csrfToken }: { node: string; isAdmin: boolean; csrfToken: string }) {
  const [data, setData] = useState<NodeData | null>(null);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<Job | "new" | null>(null);
  const [history, setHistory] = useState<Job | null>(null);
  const [log, setLog] = useState<{ jobId: string; runId: string } | null>(null);
  const [adopting, setAdopting] = useState<SystemEntry | null>(null);
  const [busy, setBusy] = useState("");
  const load = useCallback(() => api<NodeData>(`/nodes/${node}`, csrfToken).then(value => { setData(value); setError(""); }).catch(failure => setError(failure.message)), [node, csrfToken]);
  useEffect(() => { void load(); }, [load]);
  const act = async (key: string, action: () => Promise<void>) => { setBusy(key); setError(""); try { await action(); await load(); } catch (failure) { setError(failure instanceof Error ? failure.message : "Mislukt."); } finally { setBusy(""); } };
  const now = Date.now() / 1000;
  if (!data) return error ? <p className="config-error" role="alert">{error}</p> : <p role="status">Laden…</p>;
  return <>
    {error && <p className="config-error" role="alert">{error}</p>}
    <div className="cron-heading"><h4>ControlDeck-cronjobs op {node}</h4>{isAdmin && <button type="button" className="primary" onClick={() => setEditing("new")}>+ Nieuwe cronjob</button>}</div>
    {data.jobs.length === 0 ? <p>Nog geen ControlDeck-cronjobs op deze node.{isAdmin ? " Maak er een aan, of neem hieronder een bestaande cronjob over." : ""}</p> :
      <div className="task-table"><table>
        <thead><tr><th>Job</th><th>Schema</th><th>Volgende</th><th>Laatste run</th>{isAdmin && <th>Acties</th>}</tr></thead>
        <tbody>{data.jobs.map(job => {
          const missed = isMissed(job.schedule, job.enabled, job.createdAt, job.lastRun?.start, now);
          const last = job.lastRun ? runStatus(job.lastRun) : null;
          const next = job.enabled ? nextRuns(job.schedule, new Date(), 1)[0] : null;
          return <tr key={job.id} className={missed || last?.level === "error" ? "task-error" : undefined}>
            <td><strong>{job.id}</strong>{job.description && <div className="muted">{job.description}</div>}{job.adopted && <div className="muted">Overgenomen uit {job.adoptedFrom}</div>}{isAdmin && job.command && <code className="cron-command">{job.command}</code>}</td>
            <td>{describeCron(job.schedule)}<div className="muted"><code>{job.schedule}</code> · {job.user}</div></td>
            <td>{!job.enabled ? <span className="task-status warning">⏸ Gepauzeerd</span> : next ? time(next.getTime() / 1000) : "—"}</td>
            <td>{missed ? <span className="task-status error">△ Gemist</span> : last ? <span className={`task-status ${last.level === "ok" ? "ok" : last.level === "error" ? "error" : ""}`}>{last.label}</span> : "Nog niet gedraaid"}<div className="muted">{job.lastRun ? `${time(job.lastRun.start)}${job.lastRun.duration != null ? ` · ${duration(0, job.lastRun.duration, 0)}` : ""}` : ""}</div></td>
            {isAdmin && <td className="cron-actions">
              <button type="button" disabled={!!busy} onClick={() => { if (window.confirm(`Job ${job.id} nu uitvoeren op ${node}?\n\n${job.command ?? ""}`)) void act(`run-${job.id}`, async () => { const result = await api<{ runId: string }>(`/nodes/${node}/jobs/${job.id}/run`, csrfToken, "POST"); setLog({ jobId: job.id, runId: result.runId }); }); }}>Nu uitvoeren</button>
              <button type="button" disabled={!!busy} onClick={() => void act(`pause-${job.id}`, async () => { await api(`/nodes/${node}/jobs/${job.id}/pause`, csrfToken, "POST", { enabled: !job.enabled }); })}>{job.enabled ? "Pauzeren" : "Hervatten"}</button>
              <button type="button" disabled={!!busy} onClick={() => setEditing(job)}>Bewerken</button>
              <button type="button" disabled={!!busy} onClick={() => setHistory(job)}>Geschiedenis</button>
              {job.adopted
                ? <button type="button" disabled={!!busy} onClick={() => { if (window.confirm(`Job ${job.id} teruggeven? De oorspronkelijke regel in ${job.adoptedFrom} wordt weer actief en de ControlDeck-job verdwijnt (met zijn geschiedenis).`)) void act(`release-${job.id}`, async () => { await api(`/nodes/${node}/jobs/${job.id}/release`, csrfToken, "POST"); }); }}>Teruggeven</button>
                : <button type="button" className="danger-link" disabled={!!busy} onClick={() => { if (window.confirm(`Job ${job.id} op ${node} verwijderen?\n\nSchema: ${describeCron(job.schedule)}\nCommando: ${job.command ?? ""}\n\nDe geschiedenis van deze job verdwijnt ook.`)) void act(`delete-${job.id}`, async () => { await api(`/nodes/${node}/jobs/${job.id}`, csrfToken, "DELETE"); }); }}>Verwijderen</button>}
            </td>}
          </tr>;
        })}</tbody></table></div>}

    <h4>Overige cronjobs op {node}</h4>
    <p className="health-ok">Alleen-lezen. Van deze jobs is alleen te zien dát ze starten (in de clustertijdlijn), niet het resultaat.{isAdmin ? " Met Overnemen beheert ControlDeck de job, met logging en monitoring; de oorspronkelijke regel wordt uitgezet met een back-up." : ""}</p>
    {data.system.length === 0 ? <p>Geen.</p> : <div className="task-table plain"><table>
      <thead><tr><th>Bron</th><th>Schema</th><th>Gebruiker</th>{isAdmin && <><th>Commando</th><th></th></>}</tr></thead>
      <tbody>{data.system.map(entry => <tr key={entry.ref}>
        <td><code>{entry.source}</code></td><td>{describeCron(entry.schedule)}<div className="muted"><code>{entry.schedule}</code></div></td><td>{entry.user}</td>
        {isAdmin && <><td><code className="cron-command">{entry.command}</code></td><td>{entry.schedule.startsWith("@reboot") ? <span className="muted">bij opstarten</span> : <button type="button" disabled={!!busy} onClick={() => setAdopting(entry)}>Overnemen</button>}</td></>}
      </tr>)}</tbody></table></div>}

    {data.timers.length > 0 && <details className="cron-timers"><summary>Systemd-timers ({data.timers.length})</summary><div className="task-table plain"><table>
      <thead><tr><th>Timer</th><th>Start</th><th>Volgende</th><th>Laatste</th></tr></thead>
      <tbody>{data.timers.map(timer => <tr key={timer.unit}><td>{timer.unit}</td><td>{timer.activates}</td><td>{time(timer.next)}</td><td>{time(timer.last)}</td></tr>)}</tbody></table></div></details>}

    {editing && <JobForm node={node} job={editing === "new" ? null : editing} csrfToken={csrfToken} existing={data.jobs.map(job => job.id)} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); void load(); }}/>}
    {history && <HistoryModal node={node} job={history} isAdmin={isAdmin} csrfToken={csrfToken} onClose={() => setHistory(null)} onLog={runId => setLog({ jobId: history.id, runId })}/>}
    {log && <LogModal node={node} {...log} csrfToken={csrfToken} onClose={() => { setLog(null); void load(); }}/>}
    {adopting && <AdoptModal node={node} entry={adopting} csrfToken={csrfToken} onClose={() => setAdopting(null)} onDone={() => { setAdopting(null); void load(); }}/>}
  </>;
}

const MODES: { mode: Picker["mode"]; label: string }[] = [{ mode: "minutes", label: "Elke N minuten" }, { mode: "hourly", label: "Elk uur" }, { mode: "daily", label: "Dagelijks" }, { mode: "weekly", label: "Wekelijks" }, { mode: "monthly", label: "Maandelijks" }, { mode: "advanced", label: "Geavanceerd" }];
const DEFAULTS: Record<Picker["mode"], Picker> = { minutes: { mode: "minutes", every: 15 }, hourly: { mode: "hourly", minute: 0 }, daily: { mode: "daily", time: "02:00" }, weekly: { mode: "weekly", days: [1], time: "02:00" }, monthly: { mode: "monthly", day: 1, time: "02:00" }, advanced: { mode: "advanced", expression: "0 2 * * *" } };

function JobForm({ node, job, csrfToken, existing, onClose, onSaved }: { node: string; job: Job | null; csrfToken: string; existing: string[]; onClose: () => void; onSaved: () => void }) {
  const [id, setId] = useState(job?.id ?? "");
  const [description, setDescription] = useState(job?.description ?? "");
  const [command, setCommand] = useState(job?.command ?? "");
  const [user, setUser] = useState(job?.user ?? "root");
  const [picker, setPicker] = useState<Picker>(job ? pickerFor(job.schedule) : DEFAULTS.daily);
  const [logs, setLogs] = useState(job?.logs ?? true);
  const [timeout, setTimeoutMinutes] = useState(job?.timeoutMinutes ? String(job.timeoutMinutes) : "");
  const [enabled, setEnabled] = useState(job?.enabled ?? true);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const schedule = buildCron(picker);
  const idValid = /^[a-z0-9][a-z0-9-]{0,39}$/.test(id) && (job !== null || !existing.includes(id));
  const valid = idValid && !!schedule && command.trim().length > 0 && command.length <= 1000 && /^[a-z_][a-z0-9_-]{0,31}$/.test(user) && (timeout === "" || (/^\d+$/.test(timeout) && Number(timeout) >= 1 && Number(timeout) <= 1440));
  const save = async () => {
    setBusy(true); setError("");
    try {
      await api(`/nodes/${node}/jobs/${id}`, csrfToken, "PUT", { description, schedule, user, command, logs, enabled, timeoutMinutes: timeout ? Number(timeout) : null });
      onSaved();
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Opslaan mislukt."); setConfirming(false); } finally { setBusy(false); }
  };
  const set = (patch: Partial<Picker>) => setPicker({ ...picker, ...patch } as Picker);
  return <Modal open title={job ? `Cronjob ${job.id} bewerken` : `Nieuwe cronjob op ${node}`} onClose={onClose}>
    {!confirming ? <form className="bookmark-form in-modal cron-form" onSubmit={event => { event.preventDefault(); if (valid) setConfirming(true); }}>
      <label>Naam<input value={id} disabled={!!job} onChange={event => setId(event.target.value.toLowerCase())} placeholder="backup-database" maxLength={40} required/>{!job && id && !idValid && <small className="task-message">Kleine letters, cijfers en '-', uniek op deze node.</small>}</label>
      <label>Omschrijving (optioneel)<input value={description} onChange={event => setDescription(event.target.value)} maxLength={200}/></label>
      <fieldset className="cron-picker"><legend>Schema</legend>
        <div className="cron-modes">{MODES.map(item => <label key={item.mode} className="checkbox"><input type="radio" name="mode" checked={picker.mode === item.mode} onChange={() => setPicker(item.mode === "advanced" ? { mode: "advanced", expression: schedule ?? "0 2 * * *" } : DEFAULTS[item.mode])}/> {item.label}</label>)}</div>
        {picker.mode === "minutes" && <label>Elke<select value={picker.every} onChange={event => set({ every: Number(event.target.value) })}>{[1, 2, 5, 10, 15, 20, 30].map(value => <option key={value} value={value}>{value} {value === 1 ? "minuut" : "minuten"}</option>)}</select></label>}
        {picker.mode === "hourly" && <label>Op minuut<input type="number" min={0} max={59} value={picker.minute} onChange={event => set({ minute: Number(event.target.value) })}/></label>}
        {(picker.mode === "daily" || picker.mode === "weekly" || picker.mode === "monthly") && <label>Om<input type="time" value={picker.time} onChange={event => set({ time: event.target.value })}/></label>}
        {picker.mode === "weekly" && <div className="cron-days">{[1, 2, 3, 4, 5, 6, 0].map(day => <label key={day} className="checkbox"><input type="checkbox" checked={picker.days.includes(day)} onChange={event => set({ days: event.target.checked ? [...picker.days, day] : picker.days.filter(item => item !== day) })}/> {DAY_LABELS[day].slice(0, 2)}</label>)}</div>}
        {picker.mode === "monthly" && <label>Op dag<input type="number" min={1} max={28} value={picker.day} onChange={event => set({ day: Number(event.target.value) })}/></label>}
        {picker.mode === "advanced" && <label>Cronregel (minuut uur dag maand weekdag)<input value={picker.expression} onChange={event => set({ expression: event.target.value })} spellCheck={false}/></label>}
        <p className="cron-preview">{schedule ? <><strong>{describeCron(schedule)}</strong> · <code>{schedule}</code><br/>Volgende: {nextRuns(schedule, new Date(), 5).map(date => time(date.getTime() / 1000)).join(" · ") || "geen binnen vier jaar"}</> : <span className="task-message">Onvolledig of ongeldig schema.</span>}</p>
      </fieldset>
      <label>Commando (één regel, wordt uitgevoerd met /bin/sh)<input value={command} onChange={event => setCommand(event.target.value)} maxLength={1000} spellCheck={false} required placeholder="/usr/local/bin/backup.sh"/></label>
      <div className="cron-row">
        <label>Gebruiker<input value={user} onChange={event => setUser(event.target.value.trim())} maxLength={32}/></label>
        <label>Time-out in minuten (optioneel)<input value={timeout} onChange={event => setTimeoutMinutes(event.target.value)} inputMode="numeric" placeholder="geen"/></label>
      </div>
      <label className="checkbox"><input type="checkbox" checked={logs} onChange={event => setLogs(event.target.checked)}/> Uitvoer bewaren (laatste 20 runs, maximaal 14 dagen)</label>
      <label className="checkbox"><input type="checkbox" checked={enabled} onChange={event => setEnabled(event.target.checked)}/> Actief</label>
      {error && <p className="config-error" role="alert">{error}</p>}
      <div className="form-actions"><button disabled={!valid}>Controleren</button><button type="button" onClick={onClose}>Annuleren</button></div>
    </form> : <section className="cron-confirm">
      <p>Controleer de cronjob. Hij draait als <strong>{user}</strong> op <strong>{node}</strong>{user === "root" ? " met volledige rechten" : ""}.</p>
      <dl><dt>Naam</dt><dd>{id}</dd><dt>Schema</dt><dd>{schedule && describeCron(schedule)} (<code>{schedule}</code>)</dd><dt>Commando</dt><dd><code>{command}</code></dd><dt>Status</dt><dd>{enabled ? "Actief" : "Gepauzeerd"}</dd></dl>
      <div className="form-actions"><button className="primary" disabled={busy} onClick={() => void save()}>{busy ? "Opslaan…" : "Bevestigen en opslaan"}</button><button type="button" disabled={busy} onClick={() => setConfirming(false)}>Terug</button></div>
    </section>}
  </Modal>;
}

function HistoryModal({ node, job, isAdmin, csrfToken, onClose, onLog }: { node: string; job: Job; isAdmin: boolean; csrfToken: string; onClose: () => void; onLog: (runId: string) => void }) {
  const [runs, setRuns] = useState<CronRun[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api<{ runs: CronRun[] }>(`/nodes/${node}/jobs/${job.id}/history`, csrfToken).then(data => setRuns(data.runs)).catch(failure => setError(failure.message)); }, [node, job.id, csrfToken]);
  return <Modal open title={`Geschiedenis van ${job.id}`} onClose={onClose}>
    {error && <p className="config-error" role="alert">{error}</p>}
    {!runs ? <p role="status">Laden…</p> : runs.length === 0 ? <p>Nog geen runs.</p> : <div className="task-table plain"><table>
      <thead><tr><th>Resultaat</th><th>Start</th><th>Duur</th><th>Aanleiding</th>{isAdmin && <th>Log</th>}</tr></thead>
      <tbody>{runs.map(run => { const status = runStatus(run); return <tr key={run.runId}><td><span className={`task-status ${status.level === "ok" ? "ok" : status.level === "error" ? "error" : ""}`}>{status.label}</span></td><td>{time(run.start)}</td><td>{run.duration != null ? duration(0, run.duration, 0) : "—"}</td><td>{run.trigger === "manual" ? "Handmatig" : "Schema"}</td>{isAdmin && <td><button type="button" className="task-more" onClick={() => onLog(run.runId!)}>bekijken</button></td>}</tr>; })}</tbody></table></div>}
  </Modal>;
}

/** Live log: polls the agent from the last offset until the run is finished. */
function LogModal({ node, jobId, runId, csrfToken, onClose }: { node: string; jobId: string; runId: string; csrfToken: string; onClose: () => void }) {
  const [content, setContent] = useState("");
  const [status, setStatus] = useState<{ status: string; exitCode: number | null }>({ status: "running", exitCode: null });
  const [error, setError] = useState("");
  useEffect(() => {
    let offset = 0, stopped = false;
    const poll = async () => {
      try {
        const data = await api<{ content: string; offset: number; status: string; exitCode: number | null }>(`/nodes/${node}/jobs/${jobId}/runs/${runId}/log?offset=${offset}`, csrfToken);
        if (stopped) return;
        offset = data.offset; setContent(previous => previous + data.content); setStatus({ status: data.status, exitCode: data.exitCode }); setError("");
        if (data.status === "running" || data.status === "pending") setTimeout(() => void poll(), 1000);
      } catch (failure) { if (!stopped) { setError(failure instanceof Error ? failure.message : "Log niet beschikbaar."); setTimeout(() => void poll(), 3000); } }
    };
    void poll();
    return () => { stopped = true; };
  }, [node, jobId, runId, csrfToken]);
  const state = runStatus(status);
  return <Modal open title={`Log van ${jobId} op ${node}`} onClose={onClose}>
    <p><span className={`task-status ${state.level === "ok" ? "ok" : state.level === "error" ? "error" : ""}`}>{status.status === "pending" ? "◌ Starten…" : state.label}</span> <span className="muted">run {runId}</span></p>
    {error && <p className="config-error" role="alert">{error}</p>}
    <pre className="cron-log" aria-live="polite">{content || (status.status === "running" || status.status === "pending" ? "Wachten op uitvoer…" : "Geen uitvoer.")}</pre>
  </Modal>;
}

function AdoptModal({ node, entry, csrfToken, onClose, onDone }: { node: string; entry: SystemEntry; csrfToken: string; onClose: () => void; onDone: () => void }) {
  const [id, setId] = useState(suggestJobId(entry.command));
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return <Modal open title={`Cronjob overnemen op ${node}`} onClose={onClose}>
    <p>ControlDeck maakt een eigen job met hetzelfde schema en commando, met logging en monitoring. De oorspronkelijke regel in <code>{entry.source}</code> wordt uitgecommentarieerd (met een back-up op de node). Met <strong>Teruggeven</strong> zet je hem later precies terug.</p>
    <dl><dt>Schema</dt><dd>{describeCron(entry.schedule)} (<code>{entry.schedule}</code>)</dd><dt>Gebruiker</dt><dd>{entry.user}</dd><dt>Commando</dt><dd><code>{entry.command}</code></dd></dl>
    <label>Naam van de nieuwe job<input value={id} onChange={event => setId(event.target.value.toLowerCase())} maxLength={40}/></label>
    {error && <p className="config-error" role="alert">{error}</p>}
    <div className="form-actions"><button className="primary" disabled={busy || !/^[a-z0-9][a-z0-9-]{0,39}$/.test(id)} onClick={() => { setBusy(true); setError(""); api(`/nodes/${node}/adopt`, csrfToken, "POST", { ref: entry.ref, id }).then(onDone).catch(failure => { setError(failure.message); setBusy(false); }); }}>{busy ? "Overnemen…" : "Bevestigen en overnemen"}</button><button type="button" onClick={onClose}>Annuleren</button></div>
  </Modal>;
}
