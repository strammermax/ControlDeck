import type {GridCell} from "./layout-grid.ts";

/** Pages with a personal, server-stored layout. The server keeps the same list. */
export const layoutPages = ["bookmarks", "proxmox", "media"] as const;
export type LayoutPage = typeof layoutPages[number];
/** A cell inside one named group of a page (e.g. a bookmark collection). Single-grid pages use group "main". */
export type PageLayoutCell = GridCell & {group: string};

export async function pageLayoutRequest(page: LayoutPage, csrf = "", method: "GET" | "PUT" | "DELETE" = "GET", cells?: PageLayoutCell[], signal?: AbortSignal): Promise<PageLayoutCell[]> {
  if (!(layoutPages as readonly string[]).includes(page)) throw new TypeError("Onbekende pagina-indeling.");
  const response = await fetch(`/api/layouts/${page}`, {
    method, cache: "no-store", signal,
    headers: {"Content-Type": "application/json", ...(method === "GET" ? {} : {"X-CSRF-Token": csrf})},
    body: method === "PUT" ? JSON.stringify({cells}) : undefined,
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof result.error === "string" ? result.error : "Indeling niet beschikbaar.");
  return Array.isArray(result.cells) ? result.cells : [];
}

export function groupCells(cells: PageLayoutCell[], group: string): GridCell[] {
  return cells.filter(cell => cell.group === group).map(({id, x, y, width, height}) => ({id, x, y, width, height}));
}

export function withGroupCells(cells: PageLayoutCell[], group: string, next: GridCell[]): PageLayoutCell[] {
  return [...cells.filter(cell => cell.group !== group), ...next.map(cell => ({...cell, group}))];
}
