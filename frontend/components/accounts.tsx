"use client";
import { useCallback, useEffect, useState } from "react";

type Account = { firstName: string; lastName: string; email: string; role: "admin" | "editor" | "user"; enabled: boolean; ssoType: "google" | "windows"; modules: string[] };
const empty: Account = { firstName: "", lastName: "", email: "", role: "user", enabled: true, ssoType: "google", modules: ["*"] };
export function Accounts({ csrfToken }: { csrfToken: string }) {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [profile, setProfile] = useState<Account>(empty);
  const [editing, setEditing] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    try { const response = await fetch("/api/accounts", {cache:"no-store"}); if (!response.ok) throw new Error(); setAccounts(await response.json()); }
    catch { setMessage("De gebruikers kunnen niet worden geladen."); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  const save = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setMessage("");
    try {
      const response = await fetch(editing ? `/api/accounts/${encodeURIComponent(editing)}` : "/api/accounts", { method: editing ? "PUT" : "POST", headers: {"Content-Type":"application/json", "X-CSRF-Token":csrfToken}, body: JSON.stringify(profile) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? "Opslaan mislukt.");
      setMessage("Profiel opgeslagen."); setProfile(empty); setEditing(null); await load();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Opslaan mislukt."); }
    finally { setBusy(false); }
  };
  return <div className="accounts">
    <p>Admins beheren gebruikers. Users gebruiken de toegestane onderdelen en bewaren hun eigen voorkeuren.</p>
    <div className="account-table"><table><thead><tr><th>Naam</th><th>E-mail</th><th>Rechten</th><th>Ingeschakeld</th><th>SSO</th><th></th></tr></thead><tbody>{accounts.map(item => <tr key={item.email}><td>{`${item.firstName} ${item.lastName}`.trim() || "—"}</td><td>{item.email}</td><td>{item.role}</td><td>{item.enabled ? "Ja" : "Nee"}</td><td>{item.ssoType}</td><td><button onClick={() => {setProfile(item); setEditing(item.email); setMessage("");}}>Bewerken</button></td></tr>)}</tbody></table></div>
    <form onSubmit={save}><h3>{editing ? "Gebruiker bewerken" : "Gebruiker aanmaken"}</h3>
      <label>Voornaam<input maxLength={100} value={profile.firstName} onChange={event => setProfile({...profile, firstName:event.target.value})}/></label>
      <label>Achternaam<input maxLength={100} value={profile.lastName} onChange={event => setProfile({...profile, lastName:event.target.value})}/></label>
      <label>E-mail<input type="email" required maxLength={254} value={profile.email} onChange={event => setProfile({...profile, email:event.target.value})}/></label>
      <label>Rechten<select value={profile.role} onChange={event => setProfile({...profile, role:event.target.value as Account["role"]})}><option value="user">User</option><option value="editor">Editor</option><option value="admin">Admin</option></select></label>
      <label>SSO-type<select value={profile.ssoType} onChange={event => setProfile({...profile, ssoType:event.target.value as Account["ssoType"]})}><option value="google">Google</option><option value="windows">Windows (koppeling volgt)</option></select></label>
      <label className="checkbox"><input type="checkbox" checked={profile.enabled} onChange={event => setProfile({...profile, enabled:event.target.checked})}/>Ingeschakeld</label>
      <div className="form-actions"><button type="submit" disabled={busy}>{busy ? "Opslaan…" : "Opslaan"}</button>{editing && <button type="button" onClick={() => {setEditing(null); setProfile(empty);}}>Annuleren</button>}</div>
    </form>
    {message && <p role="status">{message}</p>}
  </div>;
}
