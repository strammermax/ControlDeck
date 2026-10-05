export type AgentNodeState = "ready" | "outdated" | "not_installed" | "not_enrolled" | "hostkey_changed" | "unreachable";
export type AgentNode = { node: string; address: string; fingerprint?: string; state?: AgentNodeState };
export type AgentOverview = { proxy: boolean; error?: string; updateCommand?: string; keyExists?: boolean; publicKey?: string | null; nodes: AgentNode[]; suggestions: { node: string; address: string }[]; agentVersion?: number };

/** Per node row in the wizard: enrolled state if known, otherwise "not enrolled"; suggestions from Proxmox fill the gaps. */
export function agentRows(overview: AgentOverview): AgentNode[] {
  if (!overview || !Array.isArray(overview.nodes) || !Array.isArray(overview.suggestions)) throw new TypeError("Invalid overview");
  const rows = new Map<string, AgentNode>();
  for (const suggestion of overview.suggestions) rows.set(suggestion.node, { node: suggestion.node, address: suggestion.address, state: "not_enrolled" });
  for (const node of overview.nodes) rows.set(node.node, { ...node, state: node.state ?? "unreachable" });
  return [...rows.values()].sort((a, b) => a.node.localeCompare(b.node));
}

export function agentStateText(state: AgentNodeState | undefined): { label: string; level: "ok" | "warning" | "error" | "unknown"; hint: string } {
  switch (state) {
    case "ready": return { label: "Klaar", level: "ok", hint: "De agent antwoordt. Deze node kan cronjobs beheren." };
    case "outdated": return { label: "Agent verouderd", level: "warning", hint: "Voer het installatiecommando opnieuw uit om de agent bij te werken." };
    case "not_installed": return { label: "Agent nog niet geïnstalleerd", level: "warning", hint: "Voer het installatiecommando uit in de shell van de node en test opnieuw." };
    case "hostkey_changed": return { label: "Hostsleutel veranderd", level: "error", hint: "Controleer waarom de node een andere SSH-hostsleutel heeft. Ontkoppel en koppel daarna opnieuw." };
    case "unreachable": return { label: "Niet bereikbaar", level: "error", hint: "Controleer of de node aan staat en SSH (poort 22) bereikbaar is vanaf ControlDeck." };
    default: return { label: "Nog niet gekoppeld", level: "unknown", hint: "Lees de hostsleutel en bevestig de vingerafdruk." };
  }
}
