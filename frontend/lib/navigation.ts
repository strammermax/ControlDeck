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
