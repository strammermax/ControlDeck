export const proxmoxViews = {health: "ProxMenux - gezondheid en sensoren", nodes: "Nodes · CPU en geheugen", guests: "Gasten · hoogste CPU-gebruik", tasks: "Taken · fouten en waarschuwingen", all: "Volledig clusteroverzicht"} as const;
export type ProxmoxView = keyof typeof proxmoxViews;
export function proxmoxView(value: unknown): ProxmoxView {
  if (typeof value !== "string" || !Object.hasOwn(proxmoxViews, value)) throw new Error("Kies een geldige Proxmox-weergave.");
  return value as ProxmoxView;
}
