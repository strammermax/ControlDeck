"use client";
import { useEffect, useState } from "react";
import { cleanAddress } from "../lib/proxmox";

type Certificate = { url: string; fingerprint: string; trusted: boolean };
type Details = { version: string; cluster: string | null; nodes: { name: string; online: boolean }[]; guests: { qemu: number; lxc: number }; missingPrivileges: string[]; extraPrivileges: string[] };
type Stored = { connected: boolean; url?: string; fingerprint?: string | null; tokenId?: string; connectedAt?: number };
const STEPS = ["Module", "Verbinding", "Toegang", "Controleren", "Koppelen"];

async function call<T>(path: string, csrfToken: string, method = "GET", body?: unknown): Promise<T> {
  const response = await fetch(`/api/proxmox/connection${path}`, { cache: "no-store", method, headers: body ? { "Content-Type": "application/json", "X-CSRF-Token": csrfToken } : method !== "GET" ? { "X-CSRF-Token": csrfToken } : undefined, body: body ? JSON.stringify(body) : undefined });
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(typeof data?.error === "string" ? data.error : "Proxmox-koppeling niet beschikbaar.");
  return data;
}

/** Wizard steps 2–5 for the read-only Proxmox connection. The token secret is sent once and never returned. */
export function ProxmoxConnect({ csrfToken, onBack }: { csrfToken: string; onBack: () => void }) {
  const [step, setStep] = useState(2);
  const [stored, setStored] = useState<Stored | null>(null);
  const [url, setUrl] = useState("https://192.168.1.98:8006");
  const [certificate, setCertificate] = useState<Certificate | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [tokenId, setTokenId] = useState("");
  const [secret, setSecret] = useState("");
  const [details, setDetails] = useState<Details | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    call<Stored>("", csrfToken).then(data => { setStored(data); if (data.connected) { setUrl(data.url ?? ""); setTokenId(data.tokenId ?? ""); } }).catch(failure => setError(failure.message));
  }, [csrfToken]);
  const run = async (action: () => Promise<void>) => { setBusy(true); setError(""); try { await action(); } catch (failure) { setError(failure instanceof Error ? failure.message : "Er ging iets mis."); } finally { setBusy(false); } };
  const connection = () => ({ url: certificate?.url ?? url, fingerprint: certificate && !certificate.trusted ? certificate.fingerprint : null, tokenId, ...(secret ? { secret } : {}) });
  const reuseSecret = !!stored?.connected && stored.tokenId === tokenId;

  return <>
    <ol className="wizard-progress" aria-label="Koppelstappen">{STEPS.map((label, index) => <li key={label} aria-current={step === index + 1 ? "step" : undefined}>{index + 1}. {label}</li>)}</ol>
    {error && <p role="alert">{error}</p>}
    {stored?.connected && step < 5 && <p role="status">Proxmox is al gekoppeld met {stored.url} ({stored.tokenId}). Je kunt de koppeling hier vervangen.</p>}
    {step === 2 && <fieldset><legend>Verbinding</legend>
      <label>Adres van Proxmox<input value={url} onChange={event => { setUrl(event.target.value); setCertificate(null); setConfirmed(false); }} placeholder="https://192.168.1.98:8006" autoComplete="off"/></label>
      <p>Een node-adres of je eigen domein, bijvoorbeeld https://pm.vanburik.info. ControlDeck controleert eerst het certificaat.</p>
      {certificate && (certificate.trusted
        ? <p role="status">✓ Het certificaat van {certificate.url} is geldig. Er is geen vingerafdruk nodig.</p>
        : <div className="fingerprint"><p>△ {certificate.url} gebruikt een eigen (zelfondertekend) certificaat. Vergelijk deze vingerafdruk met Proxmox → node → Systeem → Certificaten → <em>pve-ssl.pem</em>:</p><code>{certificate.fingerprint}</code><label className="checkbox"><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)}/> De vingerafdruk komt overeen</label></div>)}
    </fieldset>}
    {step === 3 && <fieldset><legend>Toegang</legend>
      <p>Maak in Proxmox een alleen-lezen API-token. In een shell op een node:</p>
      <pre className="command">{`pveum user add controldeck@pve --comment "ControlDeck read-only"
pveum acl modify / --users controldeck@pve --roles PVEAuditor
pveum user token add controldeck@pve controldeck --privsep 0`}</pre>
      <p>Het laatste commando toont het geheim één keer. Plak het hieronder; deel het nergens anders.</p>
      <label>Token-ID<input value={tokenId} onChange={event => setTokenId(event.target.value.trim())} placeholder="controldeck@pve!controldeck" autoComplete="off" spellCheck={false}/></label>
      <label>Tokengeheim<input type="password" value={secret} onChange={event => setSecret(event.target.value.trim())} placeholder={reuseSecret ? "Leeg laten om het opgeslagen geheim te houden" : "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"} autoComplete="new-password" spellCheck={false}/></label>
    </fieldset>}
    {step === 4 && details && <section><h4>Controleer de koppeling</h4><dl>
      <dt>Proxmox</dt><dd>{details.version}</dd>
      <dt>Cluster</dt><dd>{details.cluster ?? "Losse node (geen cluster)"}</dd>
      <dt>Nodes</dt><dd>{details.nodes.map(node => `${node.name} ${node.online ? "✓ online" : "✗ offline"}`).join(" · ") || "—"}</dd>
      <dt>Gasten</dt><dd>{details.guests.qemu} VM's · {details.guests.lxc} containers</dd>
    </dl>
      {details.missingPrivileges.length > 0 && <p role="alert">Het token mist leesrechten: {details.missingPrivileges.join(", ")}. Geef het de rol PVEAuditor op pad /.</p>}
      {details.extraPrivileges.length > 0 && <p role="alert">△ Dit token mag meer dan lezen ({details.extraPrivileges.slice(0, 6).join(", ")}{details.extraPrivileges.length > 6 ? ", …" : ""}). ControlDeck gebruikt alleen leesrechten; een token met alleen PVEAuditor is veiliger.</p>}
    </section>}
    {step === 5 && <section aria-live="polite"><h4>Proxmox gekoppeld</h4><p>De taken van je cluster staan nu onder Proxmox → Overzicht.</p><a className="provider-open" href="#proxmox">Open Proxmox-overzicht →</a></section>}
    <div className="wizard-actions">
      {step < 5 && <button disabled={busy} onClick={() => step === 2 ? onBack() : setStep(step - 1)}>Vorige</button>}
      {step === 2 && <button disabled={busy || (!!certificate && !certificate.trusted && !confirmed)} onClick={() => certificate ? setStep(3) : void run(async () => { setCertificate(await call<Certificate>("/certificate", csrfToken, "POST", { url: cleanAddress(url) })); })}>{busy ? "Certificaat controleren…" : certificate ? "Volgende" : "Certificaat controleren"}</button>}
      {step === 3 && <button disabled={busy || !tokenId || (!secret && !reuseSecret)} onClick={() => void run(async () => { setDetails(await call<Details>("/test", csrfToken, "POST", connection())); setStep(4); })}>{busy ? "Verbinding testen…" : "Verbinding testen"}</button>}
      {step === 4 && <button disabled={busy || !details || details.missingPrivileges.length > 0} onClick={() => void run(async () => { await call<Stored>("", csrfToken, "PUT", connection()); setSecret(""); setStep(5); })}>{busy ? "Koppelen…" : "Proxmox koppelen"}</button>}
    </div>
  </>;
}
