/** Virtual Apps (Kasm) client: validates server data before rendering; credentials never reach the browser. */
export type VmState = "online" | "booting" | "offline" | "unknown";
export type VirtualApp = {id: string; name: string; description: string; icon: string | null; categories: string[]; kind: "desktop" | "app"; serverId: string | null; vm: {state: VmState} | null};
export type StartResult = {url?: string; booting?: boolean; started?: number[]};
export type VirtualSession = {id: string; appId: string | null; name: string; status: string; started: string; expires: string};
export type VirtualOverview = {apps: VirtualApp[]; sessions: VirtualSession[]; portal: string};
export class VirtualAppsError extends Error {
  readonly notConfigured: boolean;
  readonly notLinked: boolean;
  constructor(message: string, notConfigured = false, notLinked = false) { super(message); this.notConfigured = notConfigured; this.notLinked = notLinked; }
}

const VM_STATES: VmState[] = ["online", "booting", "offline", "unknown"];
const ID = /^(?:[0-9a-f]{32}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/;

function https(value: unknown): string {
  if (typeof value !== "string") throw new VirtualAppsError("Ongeldig adres.");
  const url = new URL(value);
  if (url.protocol !== "https:" || url.username || url.password) throw new VirtualAppsError("Ongeldig adres.");
  return url.href;
}

export function validateOverview(value: unknown): VirtualOverview {
  const data = value as VirtualOverview;
  if (!data || !Array.isArray(data.apps) || data.apps.length > 200 || !Array.isArray(data.sessions) || data.sessions.length > 500) throw new VirtualAppsError("Ongeldige gegevens van Virtual Apps.");
  for (const app of data.apps) {
    if (!app || !ID.test(app.id) || typeof app.name !== "string" || !app.name || app.name.length > 100 || typeof app.description !== "string" || !Array.isArray(app.categories)) throw new VirtualAppsError("Ongeldige workspace.");
    if (app.kind !== "desktop" && app.kind !== "app") throw new VirtualAppsError("Ongeldige workspace.");
    if (app.vm !== null && (!app.vm || !VM_STATES.includes(app.vm.state))) throw new VirtualAppsError("Ongeldige VM-status.");
    if (app.icon !== null) app.icon = /^data:image\/(png|jpeg|webp);base64,[A-Za-z0-9+/]+={0,2}$/.test(app.icon) ? app.icon : https(app.icon);
  }
  for (const session of data.sessions) {
    if (!session || !ID.test(session.id) || typeof session.name !== "string" || (session.appId !== null && !ID.test(session.appId))) throw new VirtualAppsError("Ongeldige sessie.");
  }
  return {apps: data.apps, sessions: data.sessions, portal: https(data.portal)};
}

/** The start link must be Kasm's own connect route on the same origin as the portal. */
export function connectLink(value: unknown, portal: string): string {
  const url = new URL(https(value)), origin = new URL(portal);
  if (url.origin !== origin.origin || url.search || !/^#\/connect\/kasm\/[A-Za-z0-9_-]+\/[A-Za-z0-9_-]+\/[A-Za-z0-9_.-]+$/.test(url.hash)) throw new VirtualAppsError("Kasm gaf geen geldige sessielink.");
  return url.href;
}

export async function virtualAppsRequest<T>(route: string, csrf = "", method = "GET", signal?: AbortSignal): Promise<T> {
  if (!/^(|\/[0-9a-f-]{32,36}\/start|\/sessions\/[0-9a-f-]{32,36}(\/open)?)$/.test(route)) throw new TypeError("Ongeldige Virtual Apps-route.");
  let response: Response;
  try {
    response = await fetch(`/api/virtual-apps${route}`, {method, cache: "no-store", signal, headers: method === "GET" ? {} : {"Content-Type": "application/json", "X-CSRF-Token": csrf}, body: method === "POST" ? "{}" : undefined});
  } catch { throw new VirtualAppsError("Virtual Apps is niet bereikbaar."); }
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new VirtualAppsError(typeof result.error === "string" ? result.error : `Virtual Apps is niet beschikbaar (status ${response.status}).`, result.notConfigured === true, result.notLinked === true);
  return result as T;
}

/** Full desktops on a VM ("werkplekken") first, then single apps; each list keeps its order. */
export function splitApps(apps: VirtualApp[]): {desktops: VirtualApp[]; apps: VirtualApp[]} {
  return {desktops: apps.filter(app => app.kind === "desktop"), apps: apps.filter(app => app.kind !== "desktop")};
}

export const vmLabels: Record<VmState, string> = {online: "Online", booting: "Opstarten…", offline: "Offline", unknown: "Status onbekend"};

/** Repeat a start request while the VM boots (HTTP 202), at most `limitMs`; returns the session link. */
export async function startWhenReady(request: () => Promise<StartResult>, onBooting: () => void, limitMs = 5 * 60 * 1000,
  wait = (ms: number) => new Promise(resolve => setTimeout(resolve, ms)), now = () => Date.now()): Promise<string> {
  const deadline = now() + limitMs;
  for (;;) {
    const result = await request();
    if (typeof result.url === "string") return result.url;
    if (!result.booting) throw new VirtualAppsError("Kasm gaf geen sessielink.");
    onBooting();
    if (now() >= deadline) throw new VirtualAppsError("De VM is na 5 minuten nog niet bereikbaar. Controleer de VM in Proxmox.");
    await wait(5000);
  }
}
