export type Connection = {
  id: string; origin: string; source: string; vmid: number | null; host: string; port: number; label: string;
  ok: boolean | null; checked: number | null; since: number | null; error: string | null; ms: number | null; ip: string | null; via: string | null;
};
export type MonitoringEvent = { at: number; id: string; ok: boolean | null; error: string | null; source: string; host: string; port: number };
export type MonitoringOverview = { connections: Connection[]; events: MonitoringEvent[]; checkedAt: number | null; sourceErrors: { source: string; error: string }[] };
export type Level = "ok" | "error" | "unknown";

/** Status per connection. Never checked, or the check itself failed, is "unknown" — never shown as up or down. */
export function connectionStatus(connection: Pick<Connection, "ok" | "checked">): { label: string; level: Level } {
  if (!connection.checked) return { label: "Nog niet gecontroleerd", level: "unknown" };
  if (connection.ok === true) return { label: "✓ Online", level: "ok" };
  if (connection.ok === false) return { label: "✗ Onderbroken", level: "error" };
  return { label: "? Onbekend", level: "unknown" };
}

/** One group per source app; broken groups first, then by name. */
export function groupBySource(connections: Connection[]): { source: string; connections: Connection[]; down: number; unknown: number }[] {
  if (!Array.isArray(connections)) throw new TypeError("Invalid connections");
  const groups = new Map<string, Connection[]>();
  for (const connection of connections) groups.set(connection.source, [...(groups.get(connection.source) ?? []), connection]);
  return [...groups.entries()].map(([source, items]) => ({
    source,
    connections: [...items].sort((a, b) => rank(a) - rank(b) || a.host.localeCompare(b.host) || a.port - b.port),
    down: items.filter(item => connectionStatus(item).level === "error").length,
    unknown: items.filter(item => connectionStatus(item).level === "unknown").length,
  })).sort((a, b) => Number(b.down > 0) - Number(a.down > 0) || a.source.localeCompare(b.source));
}

const rank = (connection: Connection) => ({ error: 0, unknown: 1, ok: 2 })[connectionStatus(connection).level];

export function summarize(connections: Connection[]): { total: number; ok: number; down: number; unknown: number } {
  const levels = connections.map(connection => connectionStatus(connection).level);
  return { total: levels.length, ok: levels.filter(l => l === "ok").length, down: levels.filter(l => l === "error").length, unknown: levels.filter(l => l === "unknown").length };
}

/** "sinds 3 min", "sinds 2 u", "sinds 4 d"; empty when unknown or in the future. */
export function sinceText(since: number | null, now: number): string {
  if (!since || since > now + 5) return "";
  const seconds = Math.max(0, Math.round(now - since));
  if (seconds < 60) return "sinds zojuist";
  if (seconds < 3600) return `sinds ${Math.floor(seconds / 60)} min`;
  if (seconds < 86400) return `sinds ${Math.floor(seconds / 3600)} u`;
  return `sinds ${Math.floor(seconds / 86400)} d`;
}

/** Client-side check mirroring the server rules, so the form can explain mistakes before sending. */
export function manualConnectionError(input: { source: string; host: string; port: string; vmid: string }): string {
  if (!input.source.trim()) return "Vul de bron-app in.";
  if (!/^[A-Za-z0-9](?:[A-Za-z0-9_.:-]{0,252})$/.test(input.host.trim())) return "Vul een geldige host of IP-adres in.";
  const port = Number(input.port);
  if (!Number.isInteger(port) || port < 1 || port > 65535) return "Poort moet tussen 1 en 65535 liggen.";
  if (input.vmid.trim() && !(/^\d+$/.test(input.vmid.trim()) && Number(input.vmid) >= 100)) return "Container-ID is een getal vanaf 100, of leeg.";
  return "";
}

/** "internet" for public IPs and public hostnames; "intern" for private IPs, .home/.local/.lan/.internal names and short names. */
export function scope(host: string): "intern" | "internet" {
  const name = host.toLowerCase().replace(/\.$/, "");
  const v4 = name.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (v4) {
    const [a, b] = [Number(v4[1]), Number(v4[2])];
    return a === 10 || a === 127 || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168) || (a === 169 && b === 254) || (a === 100 && b >= 64 && b <= 127) ? "intern" : "internet";
  }
  if (name.includes(":")) return /^(fc|fd|fe80|::1$)/.test(name) ? "intern" : "internet";
  if (!name.includes(".") || /\.(home|local|lan|internal|localdomain)$/.test(name) || name === "localhost") return "intern";
  return "internet";
}

export type NotifySettings = { enabled: boolean; recipients: string[]; sender: string; smtpHost: string; smtpPort: number; delayMinutes: number; learned: boolean; lastError?: string | null };

/** Recipients typed as a list separated by commas, semicolons, spaces or new lines; duplicates removed (case-insensitive). */
export function parseRecipients(text: string): { recipients: string[]; invalid: string[] } {
  const seen = new Set<string>(), recipients: string[] = [], invalid: string[] = [];
  for (const part of text.split(/[\s,;]+/).map(value => value.trim()).filter(Boolean)) {
    if (!/^[^\s@<>,;"']{1,64}@[A-Za-z0-9.-]{1,190}\.[A-Za-z]{2,24}$/.test(part)) { invalid.push(part); continue; }
    if (!seen.has(part.toLowerCase())) { seen.add(part.toLowerCase()); recipients.push(part); }
  }
  return { recipients, invalid };
}

export type MailSummary = { uid: number; from: string; address: string; subject: string; date: number | null; unread: boolean; system: string; level: "error" | "ok" | "info" };

/** Systems with their mail count and how many look like a problem; systems with problems first. */
export function mailSystems(messages: MailSummary[]): { system: string; total: number; errors: number }[] {
  if (!Array.isArray(messages)) throw new TypeError("Invalid messages");
  const counts = new Map<string, { system: string; total: number; errors: number }>();
  for (const message of messages) {
    const entry = counts.get(message.system) ?? { system: message.system, total: 0, errors: 0 };
    entry.total += 1; if (message.level === "error") entry.errors += 1;
    counts.set(message.system, entry);
  }
  return [...counts.values()].sort((a, b) => b.errors - a.errors || a.system.localeCompare(b.system));
}
