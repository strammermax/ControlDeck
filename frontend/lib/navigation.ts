export type Provider = { id: string; type: string; label: string; enabled: boolean; url: string | null };
export type Module = { id: string; enabled: boolean; title: string; description?: string; view?: "empty" | "placeholder" | "integration" | "terminal"; provider?: string; pages?: { id: string; title: string; description?: string }[] };
export type MenuItem = { id: string; label: string; icon?: string; route?: string; url?: string; children?: MenuItem[] };
export type Configuration = {
  schemaVersion: number;
  site: { title: string; subtitle: string; logo: string; defaultTheme: "dark" | "light"; refreshSeconds: number; footerText: string; supportLabel: string; supportUrl: string };
  modules: Module[];
  menu: MenuItem[];
  providers: Provider[];
  widgets: { id: string; title: string; provider: string; route: string }[];
};
export type Destination = { id: string; label: string; description?: string; view: string; provider?: string };
export function getDestinations(config: Configuration): Destination[] {
  return config.modules.flatMap(module => [
    { id: module.id, label: module.title, description: module.description, view: module.view ?? "placeholder", provider: module.provider },
    ...(module.pages ?? []).map(page => ({ id: `${module.id}/${page.id}`, label: page.title, description: page.description, view: "placeholder", provider: module.provider })),
  ]);
}
export function firstRoute(menu: MenuItem[]): string | undefined {
  for (const item of menu) { const route = item.route ?? (item.children ? firstRoute(item.children) : undefined); if (route) return route; }
}
export function isActive(item: MenuItem, active: string): boolean {
  return item.route === active || (item.children?.some(child => isActive(child, active)) ?? false);
}
export function href(item: MenuItem): string {
  if (item.url) return item.url;
  if (item.route) return `#${item.route}`;
  throw new TypeError("Menu item has no destination");
}
/** Applies a personal top-level order; unknown ids are ignored and new items keep their configured position at the end. */
export function orderMenu(menu: MenuItem[], order: readonly string[] | undefined): MenuItem[] {
  if (!Array.isArray(menu)) throw new TypeError("Menu must be a list");
  if (!order?.length) return menu;
  const rank = new Map(order.map((id, index) => [id, index]));
  return menu.map((item, index) => ({item, index})).sort((a, b) => (rank.get(a.item.id) ?? order.length + a.index) - (rank.get(b.item.id) ?? order.length + b.index)).map(entry => entry.item);
}
/** Returns a copy with one item moved; out-of-range positions are rejected. */
export function moveItem<T>(list: readonly T[], from: number, to: number): T[] {
  if (!Number.isInteger(from) || !Number.isInteger(to) || from < 0 || to < 0 || from >= list.length || to >= list.length) throw new RangeError("Invalid position");
  const copy = [...list];
  copy.splice(to, 0, copy.splice(from, 1)[0]);
  return copy;
}
