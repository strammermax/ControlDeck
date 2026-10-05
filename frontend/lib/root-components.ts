export type RootComponents = { issues: string[]; command: string; checkout: string | null; proxy: { available: boolean; version: number | null; outdated: boolean } };

/** Banner text for outdated or missing root components; null when everything is current. */
export function rootComponentsNotice(status: RootComponents | undefined | null): { title: string; parts: string; command: string } | null {
  if (!status) return null;
  if (!Array.isArray(status.issues)) throw new TypeError("Invalid root component status");
  if (status.issues.length === 0) return null;
  return { title: "Root-onderdelen bijwerken", parts: status.issues.join(", "), command: status.command };
}
