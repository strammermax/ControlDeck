export type DashboardSection = {id: string; title: string; lane: "left" | "main" | "right"; collapsed: boolean};
type DashboardPlacement = {icon?: string;id: string; sectionId: string; x: number; y: number; width: number; height: number};
export type DashboardItem = DashboardPlacement & ({type: "link"; title: string; url: string; description: string} | {type: "app"; appId: number} | {type: "module"; moduleId: "linkwarden"; settings: {collectionId: number | null}});
export type DashboardApp = {id: number; name: string; url: string; description: string; icon: string; collection: string; summary: {label: string; value: number}[]};
export type DashboardApps = {apps: DashboardApp[]; available: boolean; warning: string | null};
export type Dashboard = {id: string; revision: number; title: string; sections: DashboardSection[]; items: DashboardItem[]};
export type DashboardList = {dashboards: Dashboard[]; defaultId: string | null};

/** Resolve only from the current authorized catalog; absent sources never fall back to stale copied fields. */
export function dashboardItemView(item: DashboardItem, apps: DashboardApp[]) {
  if (item.type === "link") return {title: item.title, url: item.url, description: item.description, icon: "", summary: [] as DashboardApp["summary"], available: true};
  if (item.type === "module") return {title: "Linkwarden", url: null, description: "Je bookmarks en collecties", icon: "", summary: [] as DashboardApp["summary"], available: true};
  const app = apps.find(value => value.id === item.appId);
  return app ? {title: app.name, url: app.url, description: app.description, icon: app.icon, summary: app.summary, available: true}
    : {title: "App niet beschikbaar", url: null, description: "De app is verwijderd, niet geladen of je hebt geen toegang meer.", icon: "", summary: [] as DashboardApp["summary"], available: false};
}

export function filterDashboardApps(apps: DashboardApp[], query: string): DashboardApp[] {
  if (typeof query !== "string" || query.length > 200) throw new TypeError("Ongeldige zoekterm.");
  const words = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  return apps.filter(app => words.every(word => `${app.name} ${app.collection} ${app.description}`.toLowerCase().includes(word)));
}

/** Requests only this feature's routes; credentials never belong in URL parameters. */
export async function dashboardRequest<T>(path = "", csrf = "", method = "GET", body?: unknown, signal?: AbortSignal): Promise<T> {
  if (!/^\/(?:[a-zA-Z0-9-]+)?$/.test(path) && path !== "") throw new TypeError("Ongeldig dashboardpad.");
  const response = await fetch(`/api/dashboards${path}`, {
    method, cache: "no-store", signal,
    headers: {"Content-Type": "application/json", ...(method === "GET" ? {} : {"X-CSRF-Token": csrf})},
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const result = await response.json().catch(() => ({}));
    throw new Error(typeof result.error === "string" ? result.error : "Dashboard niet beschikbaar. Probeer opnieuw.");
  }
  return response.json();
}

/** Coordinates are logical cells; the server independently validates the same bounds. */
export function placeItem(board: Dashboard, item: DashboardItem): Dashboard {
  if (!board.sections.some(section => section.id === item.sectionId) ||
      ![item.x, item.y, item.width, item.height].every(Number.isInteger) ||
      item.x < 0 || item.y < 0 || item.width < 1 || item.height < 1 || item.height > 6 || item.x + item.width > 12 || item.y + item.height > 100) {
    throw new RangeError("De tegel past niet op deze plaats.");
  }
  const overlap = board.items.some(other => other.id !== item.id && other.sectionId === item.sectionId &&
    item.x < other.x + other.width && item.x + item.width > other.x && item.y < other.y + other.height && item.y + item.height > other.y);
  if (overlap) throw new RangeError("Deze plaats is al bezet. Kies een vrije plaats.");
  if (!board.items.some(other => other.id === item.id) && board.items.length >= 100) throw new RangeError("Maximaal 100 tegels per dashboard.");
  return {...board, items: board.items.some(other => other.id === item.id) ? board.items.map(other => other.id === item.id ? item : other) : [...board.items, item]};
}

export function firstSpace(board: Dashboard, sectionId: string, width = 4, height = 1): {x: number; y: number} {
  if (!board.sections.some(section => section.id === sectionId) || !Number.isInteger(width) || width < 1 || width > 12 || !Number.isInteger(height) || height < 1 || height > 6) {
    throw new RangeError("Ongeldige groep of tegelgrootte.");
  }
  for (let y = 0; y <= 100 - height; y++) {
    for (let x = 0; x <= 12 - width; x++) {
      if (!board.items.some(item => item.sectionId === sectionId && x < item.x + item.width && x + width > item.x && y < item.y + item.height && y + height > item.y)) return {x, y};
    }
  }
  throw new RangeError("Deze groep is vol.");
}

export function removeSection(board: Dashboard, sectionId: string): Dashboard {
  if (!board.sections.some(section => section.id === sectionId)) throw new RangeError("Groep bestaat niet.");
  if (board.sections.length === 1) throw new RangeError("Behoud minstens één groep.");
  if (board.items.some(item => item.sectionId === sectionId)) throw new RangeError("Verplaats of verwijder eerst de tegels in deze groep.");
  return {...board, sections: board.sections.filter(section => section.id !== sectionId)};
}

/** Keep explicit form coordinates; find room when moving an existing item to a different group. */
export function configureItem(board: Dashboard, item: DashboardItem): Dashboard {
  const previous = board.items.find(value => value.id === item.id);
  return placeItem(board, {...item, ...(previous && previous.sectionId !== item.sectionId ? firstSpace(board, item.sectionId, item.width, item.height) : {})});
}

/** Protect an unfinished editor when hash navigation would unmount it. */
export function dashboardNavigation(current: string, target: string, editing: boolean, confirmDiscard: () => boolean): string {
  return current === "dashboard" && target !== current && editing && !confirmDiscard() ? current : target;
}
