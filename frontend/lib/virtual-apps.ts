/** Virtual Apps (Kasm) client: validates server data before rendering; credentials never reach the browser. */
export type VirtualApp = {id: string; name: string; description: string; icon: string | null; categories: string[]};
export type VirtualSession = {id: string; appId: string | null; name: string; status: string; started: string; expires: string};
export type VirtualOverview = {apps: VirtualApp[]; sessions: VirtualSession[]; portal: string};
export class VirtualAppsError extends Error {
  readonly notConfigured: boolean;
  readonly notLinked: boolean;
  constructor(message: string, notConfigured = false, notLinked = false) { super(message); this.notConfigured = notConfigured; this.notLinked = notLinked; }
}

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
