"use client";
import { useCallback, useEffect, useState } from "react";
import { agentRows, agentStateText, type AgentNode, type AgentOverview } from "../lib/cronjobs";

const STEPS = ["Module", "Sleutel", "Nodes", "Klaar"];

async function call<T>(path: string, csrfToken: string, method = "GET", body?: unknown): Promise<T> {
  const response = await fetch(`/api/cronjobs${path}`, { cache: "no-store", method, headers: method === "GET" ? undefined : { "Content-Type": "application/json", "X-CSRF-Token": csrfToken }, body: body ? JSON.stringify(body) : undefined });
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(typeof data?.error === "string" ? data.error : "De Cronjobs-module is niet beschikbaar.");
  return data;
}

/** Enrol nodes for the ControlDeck agent: SSH key, host key confirmation, install command, test. */
export function CronjobsConnect({ csrfToken, onBack }: { csrfToken: string; onBack: () => void }) {
  const [step, setStep] = useState(2);
  const [overview, setOverview] = useState<AgentOverview | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const load = useCallback(async () => {
    try { setOverview(await call<AgentOverview>("/agent", csrfToken)); setError(""); } catch (failure) { setError(failure instanceof Error ? failure.message : "Niet beschikbaar."); }
  }, [csrfToken]);
  useEffect(() => { void load(); }, [load]);
  const run = async (key: string, action: () => Promise<void>) => { setBusy(key); setError(""); try { await action(); } catch (failure) { setError(failure instanceof Error ? failure.message : "Er ging iets mis."); } finally { setBusy(""); } };
  const rows = overview ? agentRows(overview) : [];
  const ready = rows.filter(row => row.state === "ready").length;
  return <>
    <ol className="wizard-progress" aria-label="Koppelstappen">{STEPS.map((label, index) => <li key={label} aria-current={step === index + 1 ? "step" : undefined}>{index + 1}. {label}</li>)}</ol>
    {error && <p role="alert">{error}</p>}
    {!overview ? <p role="status">Laden…</p> : !overview.proxy ? <div className="config-error" role="alert">
      <strong>De agent-proxy draait nog niet op de ControlDeck-host.</strong> Voer eenmalig als root uit op de ControlDeck-host:<pre className="command">{overview.updateCommand ?? "bash scripts/install-wizard.sh"}</pre>Daarna <button type="button" onClick={() => void load()}>Opnieuw controleren</button>
    </div> : <>
      {step === 2 && <section>
        <h4>SSH-sleutel van ControlDeck</h4>
        <p>ControlDeck verbindt met de nodes via SSH met een eigen sleutel. Die sleutel mag op de node alleen de ControlDeck-agent starten, nooit een shell, en alleen vanaf het adres van ControlDeck. De geheime helft verlaat de ControlDeck-host nooit.</p>
        {overview.keyExists ? <><p>✓ Sleutel aanwezig.</p><pre className="command">{overview.publicKey}</pre></> : <button type="button" disabled={busy === "key"} onClick={() => void run("key", async () => { await call("/agent/key", csrfToken, "POST"); await load(); })}>{busy === "key" ? "Sleutel maken…" : "Sleutel maken"}</button>}
      </section>}
      {step === 3 && <section>
        <h4>Nodes koppelen</h4>
        <p>Per node: lees de hostsleutel, vergelijk de vingerafdruk met de node, voer het installatiecommando uit in de shell van de node en test.</p>
        {rows.length === 0 && <p>Geen nodes gevonden. Koppel eerst Proxmox VE, dan worden de nodes hier ingevuld.</p>}
        {rows.map(row => <NodeRow key={row.node} row={row} csrfToken={csrfToken} busy={busy} run={run} reload={load}/>)}
      </section>}
      {step === 4 && <section aria-live="polite"><h4>{ready ? `${ready} ${ready === 1 ? "node is" : "nodes zijn"} klaar` : "Nog geen node klaar"}</h4><p>De cronjobs per node komen onder Proxmox → Nodes (stap 4 van de module, volgt). Je kunt hier later nodes toevoegen of opnieuw testen.</p></section>}
      <div className="wizard-actions">
        {step < 4 && <button disabled={!!busy} onClick={() => step === 2 ? onBack() : setStep(step - 1)}>Vorige</button>}
        {step === 2 && <button disabled={!overview.keyExists} onClick={() => setStep(3)}>Volgende</button>}
        {step === 3 && <button disabled={!!busy} onClick={() => setStep(4)}>{ready ? "Afronden" : "Later afronden"}</button>}
        {step === 4 && <button onClick={onBack}>Terug naar modulebeheer</button>}
      </div>
    </>}
  </>;
}

function NodeRow({ row, csrfToken, busy, run, reload }: { row: AgentNode; csrfToken: string; busy: string; run: (key: string, action: () => Promise<void>) => Promise<void>; reload: () => Promise<void> }) {
  const [scanned, setScanned] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [command, setCommand] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const state = agentStateText(row.state);
  const enrolled = row.state !== "not_enrolled";
  const target = { node: row.node, address: row.address };
  return <div className="node-block">
    <div className="agent-node-head"><strong>{row.node}</strong> <span className="muted">{row.address}</span> <span className={`task-status ${state.level === "unknown" ? "" : state.level}`}>{state.level === "ok" ? "✓" : state.level === "error" ? "✗" : "△"} {state.label}</span></div>
    <p className="health-ok">{state.hint}</p>
    {!enrolled && (scanned === null
      ? <button type="button" disabled={!!busy} onClick={() => void run(`scan-${row.node}`, async () => { setScanned((await call<{ fingerprint: string }>("/agent/scan", csrfToken, "POST", target)).fingerprint); })}>{busy === `scan-${row.node}` ? "Lezen…" : "Hostsleutel lezen"}</button>
      : <div className="fingerprint">
        <p>Vergelijk met de uitvoer van dit commando in de shell van <strong>{row.node}</strong>:</p>
        <pre className="command">ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub</pre>
        <code>{scanned}</code>
        <label className="checkbox"><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)}/> De vingerafdruk komt overeen</label>
        <button type="button" disabled={!confirmed || !!busy} onClick={() => void run(`trust-${row.node}`, async () => { await call("/agent/trust", csrfToken, "POST", { ...target, fingerprint: scanned }); await reload(); })}>Node koppelen</button>
      </div>)}
    {enrolled && row.state !== "ready" && row.state !== "hostkey_changed" && <div>
      {command === null
        ? <button type="button" disabled={!!busy} onClick={() => void run(`cmd-${row.node}`, async () => { setCommand((await call<{ command: string }>("/agent/install-command", csrfToken, "POST", target)).command); })}>Installatiecommando tonen</button>
        : <><p>Plak dit in de shell van <strong>{row.node}</strong> (Proxmox → {row.node} → Shell). Het controleert de agent met SHA-256 voordat het iets installeert, en voegt de sleutel maar één keer toe.</p>
          <div className="copy-row"><pre className="command">{command}</pre><button type="button" onClick={() => { void navigator.clipboard.writeText(command).then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000); }); }}>{copied ? "✓ Gekopieerd" : "Kopiëren"}</button></div></>}
    </div>}
    {enrolled && <button type="button" disabled={!!busy} onClick={() => void run(`test-${row.node}`, async () => { await call("/agent/test", csrfToken, "POST", { node: row.node }); await reload(); })}>{busy === `test-${row.node}` ? "Testen…" : "Verbinding testen"}</button>}
  </div>;
}
