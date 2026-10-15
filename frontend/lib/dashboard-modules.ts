import {serviceWidgets} from "./service-widgets.ts";
/** Module definitions point to existing features and their existing permission. */
export const dashboardModules = [{id: "linkwarden", title: "Linkwarden", description: "Je bookmarks en collecties", permission: "bookmarks", width: 12, height: 5, settings: {collectionId: null}}, {id: "kasm", title: "Kasm", description: "Open je virtuele apps met automatische aanmelding", permission: "kasm", width: 4, height: 2, settings: {}}, {id: "nextcloud", title: "Nextcloud", description: "Open je bestanden via je Google-aanmelding", permission: "nextcloud", width: 4, height: 2, settings: {}}, {id: "proxmox", title: "Proxmox", description: "Nodes, gasten en taakresultaten uit je bestaande clusterkoppeling", permission: "proxmox", width: 6, height: 5, settings: {view: "nodes"}}, {id: "system", title: "Systeemwidget", description: "Losse meters voor CPU, geheugen, temperatuur en CPU-vermogen", permission: "proxmox", width: 12, height: 4, settings: {metric: "cpu", node: ""}}, ...serviceWidgets] as const;
export function moduleOptions(permissions: string[]) {
  return dashboardModules.filter(module => permissions.includes(module.permission));
}
