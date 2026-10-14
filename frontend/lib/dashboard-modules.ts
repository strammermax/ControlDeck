/** Module definitions point to existing features and their existing permission. */
export const dashboardModules = [{id: "linkwarden", title: "Linkwarden", description: "Je bookmarks en collecties", permission: "bookmarks", width: 12, height: 5, settings: {collectionId: null}}, {id: "kasm", title: "Kasm", description: "Open je virtuele apps met automatische aanmelding", permission: "kasm", width: 4, height: 2, settings: {}}, {id: "nextcloud", title: "Nextcloud", description: "Open je bestanden via je Google-aanmelding", permission: "nextcloud", width: 4, height: 2, settings: {}}] as const;
export function moduleOptions(permissions: string[]) {
  return dashboardModules.filter(module => permissions.includes(module.permission));
}
