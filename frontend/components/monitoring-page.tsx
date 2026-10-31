"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { connectionStatus, groupBySource, manualConnectionError, parseRecipients, scope, sinceText, summarize, type MonitoringOverview, type NotifySettings } from "../lib/monitoring";

type Props = { isAdmin: boolean; csrfToken: string; refreshSeconds: number };

const time = (seconds: number | null | undefined) => seconds ? new Date(seconds * 1000).toLocaleString("nl-NL", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "—";

async function api<T>(path: string, csrfToken: string, method = "GET", body?: unknown): Promise<T> {
  const response = await fetch(`/api/monitoring${path}`, { cache: "no-store", method, headers: method === "GET" ? undefined : { "Content-Type": "application/json", "X-CSRF-Token": csrfToken }, body: body === undefined ? undefined : JSON.stringify(body) });
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(typeof data?.error === "string" ? data.error : "Niet beschikbaar.");
  return data;
}

/** Monitoring: connections between apps, checked from the source app's own container where possible. */
export function MonitoringPage({ isAdmin, csrfToken, refreshSeconds }: Props) {
  const [data, setData] = useState<MonitoringOverview | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState(false);
  const [onlyProblems, setOnlyProblems] = useState(false);
  const [area, setArea] = useState<"" | "intern" | "internet">("");
  const load = useCallback(() => api<MonitoringOverview>("", csrfToken).then(value => { setData(value); setError(""); }).catch(failure => setError(failure.message)), [csrfToken]);
  useEffect(() => { void load(); const timer = setInterval(() => void load(), Math.max(15, refreshSeconds) * 1000); return () => clearInterval(timer); }, [load, refreshSeconds]);
  const groups = useMemo(() => groupBySource((data?.connections ?? []).filter(item => !area || scope(item.host) === area)).map(group => onlyProblems ? { ...group, connections: group.connections.filter(item => connectionStatus(item).level !== "ok") } : group).filter(group => group.connections.length), [data, onlyProblems, area]);
  const counts = summarize(data?.connections ?? []);
  const now = Date.now() / 1000;
  const run = async (action: () => Promise<unknown>) => { setBusy(true); setError(""); try { await action(); await load(); } catch (failure) { setError(failure instanceof Error ? failure.message : "Mislukt."); } finally { setBusy(false); } };

  return <section className="monitoring cronjobs">
    <h3>Verbindingen</h3>
    <div className="task-toolbar">
      <p className="cron-counts"><strong>{counts.total} verbindingen:</strong> <span className="count ok">✓ {counts.ok} online</span> · <span className={counts.down ? "count error" : "count none"}>✗ {counts.down} onderbroken</span> · <span className={counts.unknown ? "count warning" : "count none"}>? {counts.unknown} onbekend</span>{data?.checkedAt ? <span className="muted"> · laatste controle {time(data.checkedAt)}</span> : null}</p>
      <label>Soort<select value={area} onChange={event => setArea(event.target.value as typeof area)}><option value="">Alles</option><option value="intern">Intern</option><option value="internet">Internet</option></select></label>
      <label className="checkbox"><input type="checkbox" checked={onlyProblems} onChange={event => setOnlyProblems(event.target.checked)}/> Alleen problemen</label>
      {isAdmin && <button type="button" disabled={busy} onClick={() => run(() => api("/check", csrfToken, "POST"))}>{busy ? "Controleren…" : "Nu controleren"}</button>}
      {isAdmin && <button type="button" className="primary" onClick={() => setAdding(true)}>+ Verbinding</button>}
    </div>
    {error && <p className="config-error" role="alert">{error}</p>}
    {data?.sourceErrors.map(item => <p key={item.source} className="config-error" role="alert">✗ Ontdekken via {item.source} mislukt: {item.error} De vorige lijst blijft staan.</p>)}
    {isAdmin && <Notifications csrfToken={csrfToken}/>}
    {adding && <AddConnection csrfToken={csrfToken} onDone={() => { setAdding(false); void load(); }}/>}
    {!data ? <p role="status">Laden…</p> : data.connections.length === 0 ? <div className="proxmox-empty"><p>Nog geen verbindingen. Ze verschijnen na de eerste controleronde zodra bronnen in Infisical staan, of voeg er handmatig een toe.</p></div> :
      groups.length === 0 ? <p>Geen problemen. ✓</p> : groups.map(group => <div key={group.source} className="monitoring-group">
        <h4>{group.source} <span className={group.down ? "count error" : group.unknown ? "count warning" : "count ok"}>{group.down ? `✗ ${group.down} onderbroken` : group.unknown ? `? ${group.unknown} onbekend` : "✓ alles online"}</span></h4>
        <div className="task-table"><table>
          <thead><tr><th>Status</th><th>Naar</th><th>Wat</th><th>Gecontroleerd via</th><th>Details</th>{isAdmin && <th></th>}</tr></thead>
          <tbody>{group.connections.map(item => { const status = connectionStatus(item); return <tr key={item.id} className={status.level === "error" ? "task-error" : undefined}>
            <td><span className={`task-status ${status.level === "unknown" ? "warning" : status.level}`}>{status.label}</span><div className="muted">{sinceText(item.since, now)}</div></td>
            <td><code>{item.host}:{item.port}</code>{item.ip && item.ip !== item.host ? <div className="muted">→ {item.ip}</div> : null}</td>
            <td>{item.label || "—"}<div className="muted">{item.origin === "manual" ? "handmatig" : item.origin === "learned" ? "geleerd uit open verbindingen" : "ontdekt"} · {scope(item.host)}</div></td>
            <td>{item.via ?? "—"}</td>
            <td>{item.error ?? (item.ms != null ? `${item.ms} ms` : "—")}</td>
            {isAdmin && <td>{item.origin === "manual" ? <button type="button" className="task-more" disabled={busy} onClick={() => { if (window.confirm(`Verbinding ${item.source} → ${item.host}:${item.port} verwijderen?`)) void run(() => api(`/connections/${item.id}`, csrfToken, "DELETE")); }}>verwijderen</button> : null}</td>}
          </tr>; })}</tbody>
        </table></div>
      </div>)}
    {data && data.events.length > 0 && <details className="cron-timers"><summary>Laatste wijzigingen ({data.events.length})</summary>
      <div className="task-table plain"><table><tbody>{data.events.map((event, index) => { const status = connectionStatus({ ok: event.ok, checked: event.at }); return <tr key={`${event.id}-${event.at}-${index}`}>
        <td>{time(event.at)}</td><td><span className={`task-status ${status.level === "unknown" ? "warning" : status.level}`}>{status.label}</span></td><td>{event.source} → <code>{event.host}:{event.port}</code></td><td>{event.error ?? ""}</td>
      </tr>; })}</tbody></table></div></details>}
    <p className="health-ok">Controle elke minuut. &ldquo;Via bron&rdquo; betekent: getest vanuit de container van de app zelf, met diens DNS en firewallpad. &ldquo;Via ControlDeck&rdquo; is een benadering voor VM&rsquo;s en apps buiten Proxmox.</p>
  </section>;
}

function AddConnection({ csrfToken, onDone }: { csrfToken: string; onDone: () => void }) {
  const [form, setForm] = useState({ source: "", host: "", port: "", vmid: "", label: "" });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const problem = manualConnectionError(form);
    if (problem) { setError(problem); return; }
    setSaving(true);
    try {
      await api("/connections", csrfToken, "POST", { source: form.source.trim(), host: form.host.trim(), port: Number(form.port), label: form.label.trim(), vmid: form.vmid.trim() ? Number(form.vmid) : null });
      onDone();
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Mislukt."); } finally { setSaving(false); }
  };
  const field = (key: keyof typeof form, label: string, hint = "") => <label>{label}<input value={form[key]} onChange={event => setForm({ ...form, [key]: event.target.value })} placeholder={hint}/></label>;
  return <form className="cron-form monitoring-form" onSubmit={submit}><fieldset>
    <legend>Nieuwe verbinding</legend>
    {field("source", "Bron-app", "Home Assistant")}
    {field("vmid", "Container-ID van de bron (optioneel)", "106")}
    {field("host", "Naar host of IP", "192.168.1.96")}
    {field("port", "Poort", "6638")}
    {field("label", "Omschrijving (optioneel)", "Zigbee-coördinator")}
    {error && <p className="config-error" role="alert">{error}</p>}
    <div className="form-actions"><button type="submit" className="primary" disabled={saving}>{saving ? "Opslaan…" : "Opslaan"}</button><button type="button" onClick={onDone}>Annuleren</button></div>
  </fieldset></form>;
}

function Notifications({ csrfToken }: { csrfToken: string }) {
  const [settings, setSettings] = useState<NotifySettings | null>(null);
  const [recipients, setRecipients] = useState("");
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null);
  const [busy, setBusy] = useState("");
  useEffect(() => { api<NotifySettings>("/notifications", csrfToken).then(value => { setSettings(value); setRecipients(value.recipients.join(", ")); }).catch(failure => setMessage({ text: failure.message, ok: false })); }, [csrfToken]);
  if (!settings) return message ? <p className="config-error" role="alert">{message.text}</p> : null;
  const act = async (key: string, action: () => Promise<string>) => { setBusy(key); setMessage(null); try { setMessage({ text: await action(), ok: true }); } catch (failure) { setMessage({ text: failure instanceof Error ? failure.message : "Mislukt.", ok: false }); } finally { setBusy(""); } };
  const save = (event: React.FormEvent) => {
    event.preventDefault();
    const parsed = parseRecipients(recipients);
    if (parsed.invalid.length) { setMessage({ text: `Ongeldig e-mailadres: ${parsed.invalid.join(", ")}`, ok: false }); return; }
    const { lastError: _ignored, ...body } = { ...settings, recipients: parsed.recipients };
    void act("save", async () => { const value = await api<NotifySettings>("/notifications", csrfToken, "PUT", body); setSettings(value); return "Opgeslagen."; });
  };
  const set = (patch: Partial<NotifySettings>) => setSettings({ ...settings, ...patch });
  return <details className="cron-timers monitoring-notify" open={!settings.enabled}><summary>Meldingen per e-mail {settings.enabled ? "· aan" : "· uit"}</summary>
    <form className="cron-form monitoring-form" onSubmit={save}><fieldset>
      <label className="checkbox"><input type="checkbox" checked={settings.enabled} onChange={event => set({ enabled: event.target.checked })}/> Mail sturen als een verbinding wegvalt en weer terugkomt</label>
      <label>Ontvangers (gescheiden door komma&rsquo;s)<input value={recipients} onChange={event => setRecipients(event.target.value)} placeholder="homelab@vanburik.info"/></label>
      <label>Afzender<input value={settings.sender} onChange={event => set({ sender: event.target.value })}/></label>
      <label>Pas melden na (minuten onderbroken)<input type="number" min={1} max={1440} value={settings.delayMinutes} onChange={event => set({ delayMinutes: Number(event.target.value) })}/></label>
      <label className="checkbox"><input type="checkbox" checked={settings.learned} onChange={event => set({ learned: event.target.checked })}/> Ook geleerde verbindingen (kan vals alarm geven bij wisselende internetadressen)</label>
      <label>SMTP-gateway<input value={`${settings.smtpHost}:${settings.smtpPort}`} onChange={event => { const [host, port] = event.target.value.split(":"); set({ smtpHost: host ?? "", smtpPort: Number(port ?? 25) }); }}/></label>
      {settings.lastError && <p className="config-error" role="alert">Laatste verzendfout: {settings.lastError}</p>}
      {message && <p className={message.ok ? "health-ok" : "config-error"} role={message.ok ? "status" : "alert"}>{message.text}</p>}
      <div className="form-actions">
        <button type="submit" className="primary" disabled={!!busy}>{busy === "save" ? "Opslaan…" : "Opslaan"}</button>
        <button type="button" disabled={!!busy} onClick={() => void act("test", async () => { const value = await api<{ recipients: string[] }>("/notifications/test", csrfToken, "POST"); return `Testmail verstuurd naar ${value.recipients.join(", ")}.`; })}>{busy === "test" ? "Versturen…" : "Testmail versturen"}</button>
      </div>
      <p className="health-ok">Eén mail per controleronde met alles wat langer dan de wachttijd onderbroken is, en een mail bij herstel. Een controle die zelf mislukt (&ldquo;onbekend&rdquo;) geeft geen melding.</p>
    </fieldset></form>
  </details>;
}
