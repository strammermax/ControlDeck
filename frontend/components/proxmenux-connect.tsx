"use client";
import { useEffect, useState } from "react";
import { cleanAddress, monitorGuidance, type MonitorState } from "../lib/proxmox";

type Row = { name: string; url: string; token: string };
type Result = { name: string; ok: boolean; version?: string; error?: string };
type Stored = { connected: boolean; ca: string | null; nodes: { name: string; url: string }[]; suggestions: { name: string; url: string }[] };
const STEPS = ["Module", "Cluster-CA", "Nodes en installatie", "Controleren", "Koppelen"];
type Detected = { name: string; url: string; state: MonitorState };

async function call<T>(path: string, csrfToken: string, method = "GET", body?: unknown): Promise<T> {
  const response = await fetch(`/api/proxmenux/connection${path}`, { cache: "no-store", method, headers: body ? { "Content-Type": "application/json", "X-CSRF-Token": csrfToken } : undefined, body: body ? JSON.stringify(body) : undefined });
  const data = await response.json().catch(() => null);
  if (!response.ok && !Array.isArray(data?.nodes)) throw new Error(typeof data?.error === "string" ? data.error : "ProxMenux-koppeling niet beschikbaar.");
  return data;
}

/** Wizard steps 2–5 for ProxMenux Monitor. Tokens are sent once and never returned to the browser. */
export function ProxmenuxConnect({ csrfToken, onBack }: { csrfToken: string; onBack: () => void }) {
  const [step, setStep] = useState(2);
  const [stored, setStored] = useState<Stored | null>(null);
  const [ca, setCa] = useState("");
  const [rows, setRows] = useState<Row[]>([]);
  const [results, setResults] = useState<Result[] | null>(null);
  const [detected, setDetected] = useState<Detected[] | null>(null);
  const [installCommand, setInstallCommand] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    call<Stored>("", csrfToken).then(data => {
      setStored(data); setCa(data.ca ?? "");
      const source = data.nodes.length ? data.nodes : data.suggestions;
      setRows(source.length ? source.map(node => ({ ...node, token: "" })) : [{ name: "", url: "", token: "" }]);
    }).catch(failure => setError(failure.message));
  }, [csrfToken]);
  const keeps = (row: Row) => !!stored?.nodes.some(node => node.name === row.name && node.url === cleanAddress(row.url));
  const payload = () => ({ ca, nodes: rows.map(row => ({ name: row.name.trim(), url: cleanAddress(row.url), ...(row.token ? { token: row.token } : {}) })) });
  const update = (index: number, change: Partial<Row>) => { setRows(rows.map((row, i) => i === index ? { ...row, ...change } : row)); setResults(null); if (change.name !== undefined || change.url !== undefined) setDetected(null); };
  const stateOf = (row: Row) => detected?.find(item => item.name === row.name.trim())?.state;
  const detect = () => run(async () => {
    const data = await call<{ nodes: Detected[]; installCommand: string }>("/detect", csrfToken, "POST", { ca, nodes: rows.map(row => ({ name: row.name.trim(), url: cleanAddress(row.url) })) });
    setDetected(data.nodes); setInstallCommand(data.installCommand);
  });
  const run = async (action: () => Promise<void>) => { setBusy(true); setError(""); try { await action(); } catch (failure) { setError(failure instanceof Error ? failure.message : "Er ging iets mis."); } finally { setBusy(false); } };

  return <>
    <ol className="wizard-progress" aria-label="Koppelstappen">{STEPS.map((label, index) => <li key={label} aria-current={step === index + 1 ? "step" : undefined}>{index + 1}. {label}</li>)}</ol>
    {error && <p role="alert">{error}</p>}
    {stored?.connected && step < 5 && <p role="status">ProxMenux is al gekoppeld voor {stored.nodes.map(node => node.name).join(", ")}. Je kunt de koppeling hier aanpassen.</p>}
    {step === 2 && <fieldset><legend>Cluster-CA</legend>
      <p>De monitors gebruiken het Proxmox-certificaat van hun node. ControlDeck vertrouwt alleen certificaten van de CA van jouw cluster. Toon die op een willekeurige node met:</p>
      <pre className="command">cat /etc/pve/pve-root-ca.pem</pre>
      <label>Inhoud van pve-root-ca.pem<textarea rows={8} value={ca} onChange={event => setCa(event.target.value)} placeholder={"-----BEGIN CERTIFICATE-----\n…\n-----END CERTIFICATE-----"} spellCheck={false}/></label>
      <p>Dit is een openbaar certificaat, geen geheim. Gebruik niet <em>pve-root-ca.key</em>.</p>
    </fieldset>}
    {step === 3 && <fieldset><legend>Nodes</legend>
      <p>Maak per monitor een API-token: Settings → Security → API tokens. Het token wordt alleen op de ControlDeck-server bewaard.{stored?.suggestions.length && !stored.connected ? " De nodes zijn ingevuld vanuit je Proxmox-koppeling." : ""}</p>
      {rows.map((row, index) => { const guidance = monitorGuidance(stateOf(row)); return <div className="node-block" key={index}><div className="node-row">
        <label>Node<input value={row.name} onChange={event => update(index, { name: event.target.value })} placeholder="pve-amd" autoComplete="off" spellCheck={false}/></label>
        <label>Adres<input value={row.url} onChange={event => update(index, { url: event.target.value })} placeholder="https://192.168.1.98:8008" autoComplete="off" spellCheck={false}/></label>
        <label>API-token<input type="password" value={row.token} onChange={event => update(index, { token: event.target.value.trim() })} placeholder={keeps(row) ? "Leeg laten om het opgeslagen token te houden" : "eyJ…"} autoComplete="new-password" spellCheck={false}/></label>
        {rows.length > 1 && <button type="button" onClick={() => { setRows(rows.filter((_, i) => i !== index)); setDetected(null); }} aria-label={`Verwijder ${row.name || "node"}`}>✕</button>}
      </div>
        {detected && <div className={`monitor-state ${guidance.level}`}><span className={`task-status ${guidance.level === "unknown" ? "" : guidance.level}`}>{guidance.level === "ok" ? "✓" : guidance.level === "error" ? "✗" : "△"} {guidance.label}</span>
          {guidance.steps.length > 0 && <ol>{guidance.steps.map(step => <li key={step}>{step}</li>)}</ol>}
          {stateOf(row) === "absent" && installCommand && <pre className="command">{installCommand}</pre>}
        </div>}
      </div>; })}
      <div className="wizard-actions"><button type="button" onClick={() => { setRows([...rows, { name: "", url: "", token: "" }]); setDetected(null); }}>+ Node toevoegen</button><button type="button" disabled={busy || rows.some(row => !row.name || !row.url)} onClick={() => void detect()}>{busy ? "Zoeken…" : detected ? "Opnieuw controleren" : "Monitors zoeken"}</button></div>
      {detected && !rows.every(row => stateOf(row) === "ready") && <p role="status">Voer de stappen uit bij de nodes die nog niet klaar zijn en kies dan Opnieuw controleren. De officiële installer staat op github.com/MacRimi/ProxMenux.</p>}
    </fieldset>}
    {step === 4 && results && <section><h4>Controle per node</h4><ul className="pool-list">{results.map(result => <li key={result.name}>
      <span className={`task-status ${result.ok ? "ok" : "error"}`}>{result.ok ? "✓" : "✗"}</span> <strong>{result.name}</strong> — {result.ok ? `verbonden, ProxMenux ${result.version ?? ""}` : result.error}
    </li>)}</ul>{!results.every(result => result.ok) && <p role="alert">Los de fouten op en test opnieuw. Er wordt pas gekoppeld als alle nodes goed zijn.</p>}</section>}
    {step === 5 && <section aria-live="polite"><h4>ProxMenux gekoppeld</h4><p>Gezondheid, schijven en LXC-updates staan nu onder Proxmox → Overzicht.</p><a className="provider-open" href="#proxmox">Open Proxmox-overzicht →</a></section>}
    <div className="wizard-actions">
      {step < 5 && <button disabled={busy} onClick={() => step === 2 ? onBack() : setStep(step - 1)}>Vorige</button>}
      {step === 2 && <button disabled={busy || !ca.includes("BEGIN CERTIFICATE")} onClick={() => { setStep(3); if (rows.every(row => row.name && row.url)) void detect(); }}>Volgende</button>}
      {step === 3 && <button disabled={busy || rows.some(row => !row.name || !row.url || stateOf(row) !== "ready" || (!row.token && !keeps(row)))} onClick={() => void run(async () => { setResults((await call<{ nodes: Result[] }>("/test", csrfToken, "POST", payload())).nodes); setStep(4); })}>{busy ? "Nodes testen…" : "Nodes testen"}</button>}
      {step === 4 && <button disabled={busy || !results?.every(result => result.ok)} onClick={() => void run(async () => { const data = await call<{ connected?: boolean; nodes: Result[] }>("", csrfToken, "PUT", payload()); setResults(data.nodes); if (data.connected) { setRows(rows.map(row => ({ ...row, token: "" }))); setStep(5); } })}>{busy ? "Koppelen…" : "ProxMenux koppelen"}</button>}
    </div>
  </>;
}
