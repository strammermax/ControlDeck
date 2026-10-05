import type { ReactNode } from "react";

const drawings: Record<string, ReactNode> = {
  dashboard: <><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>,
  "virtual-apps": <><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 8h18M8 8v13M13 8v13M18 8v13M8 13h13M8 18h13"/></>,
  bookmarks: <><path d="m12 3 5 3-5 3-5-3 5-3Zm-6 7 5 3-5 3-5-3 5-3Zm12 0 5 3-5 3-5-3 5-3ZM1 13v5l5 3 5-3v-5m2 0v5l5 3 5-3v-5M7 6v4m10-4v4"/></>,
  proxmox: <><rect x="3" y="3" width="18" height="7" rx="1"/><rect x="3" y="14" width="18" height="7" rx="1"/><path d="M6 6h1m-1 11h1"/></>,
  media: <><ellipse cx="10" cy="5" rx="7" ry="3"/><path d="M3 5v12c0 2 3 3 7 3M17 5v6M3 11c0 2 3 3 7 3"/><path d="m15 14 6 4-6 4v-8Z"/></>,
  terminal: <><path d="m4 5 6 6-6 6m9 1h7"/></>,
  language: <><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/></>,
  layers: <><path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5"/></>,
  settings: <><circle cx="12" cy="12" r="3"/><path d="M12 2v3m0 14v3M2 12h3m14 0h3M4.9 4.9 7 7m10 10 2.1 2.1M4.9 19.1 7 17M17 7l2.1-2.1"/></>,
  admin: <><path d="M3 6h3m4 0h11M3 18h11m4 0h3"/><circle cx="8" cy="6" r="2"/><circle cx="16" cy="18" r="2"/></>,
};
/** Small original SVG drawings; no font or icon runtime dependency. */
export function Icon({ name }: { name: string }) {
  return <svg className="nav-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{drawings[name] ?? drawings.dashboard}</svg>;
}
