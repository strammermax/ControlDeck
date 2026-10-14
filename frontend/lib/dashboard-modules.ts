/** Module definitions point to existing features and their existing permission. */
export const dashboardModules = [{id: "linkwarden", title: "Linkwarden", description: "Je bookmarks en collecties", permission: "bookmarks", width: 12, height: 5}] as const;
export function moduleOptions(permissions: string[]) {
  return dashboardModules.filter(module => permissions.includes(module.permission));
}
export function collectionSetting(value: string): number | null {
  if(value === "") return null;
  if(!/^[1-9][0-9]{0,9}$/.test(value)) throw new Error("Kies een geldige collectie.");
  return Number(value);
}
