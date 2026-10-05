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

export type CronRun = { source: "controldeck" | "system" | "proxmox"; node: string; jobId?: string; description?: string; command?: string; runId?: string; start: number; end?: number | null; duration?: number | null; exitCode?: number | null; status: string; message?: string | null; trigger?: string };
export type RunLevel = "ok" | "error" | "running" | "warning" | "unknown";

/** Text and level per run status; anything unknown is never shown as OK. */
export function runStatus(run: Pick<CronRun, "status" | "exitCode">): { label: string; level: RunLevel } {
  switch (run.status) {
    case "succeeded": return { label: "✓ OK", level: "ok" };
    case "failed": return { label: run.exitCode != null ? `✗ Fout (exit ${run.exitCode})` : "✗ Fout", level: "error" };
    case "running": return { label: "◌ Bezig", level: "running" };
    case "skipped": return { label: "△ Overgeslagen (nog bezig)", level: "warning" };
    case "started": return { label: "▷ Gestart (geen resultaat)", level: "unknown" };
    default: return { label: "? Onbekend", level: "unknown" };
  }
}

/** Counters for the cluster timeline. */
export function summarizeRuns(runs: readonly CronRun[]): { total: number; ok: number; failed: number; running: number; started: number } {
  if (!Array.isArray(runs)) throw new TypeError("Runs must be a list");
  return {
    total: runs.length,
    ok: runs.filter(run => run.status === "succeeded").length,
    failed: runs.filter(run => run.status === "failed").length,
    running: runs.filter(run => run.status === "running").length,
    started: runs.filter(run => run.status === "started").length,
  };
}

export const SOURCE_LABELS: Record<CronRun["source"], string> = { controldeck: "ControlDeck", system: "Systeem-cron", proxmox: "Proxmox-backup" };

/** Suggested job name for adopting an existing cron line, e.g. "/usr/bin/vzdump --all" → "vzdump". */
export function suggestJobId(command: string | undefined): string {
  const program = (command ?? "").trim().split(/\s+/)[0]?.split("/").pop() ?? "";
  const slug = program.toLowerCase().replace(/[^a-z0-9-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40);
  return /^[a-z0-9]/.test(slug) ? slug : "overgenomen-job";
}
