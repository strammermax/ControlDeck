export type TaskStatus = "running" | "ok" | "warning" | "error";
export type ProxmoxTask = { id: string; node: string; user: string; type: string; target: string; targetType: "lxc" | "qemu" | null; targetName: string | null; start: number; end: number | null; status: TaskStatus; message: string | null };
export type TaskFilter = { node: string; status: "" | TaskStatus };

const labels: Record<string, string> = {
  vzstart: "Start", qmstart: "Start", vzstop: "Stop", qmstop: "Stop", vzshutdown: "Afsluiten", qmshutdown: "Afsluiten",
  vzreboot: "Herstart", qmreboot: "Herstart", qmreset: "Reset", qmsuspend: "Pauzeren", qmresume: "Hervatten",
  vzdump: "Backup", qmigrate: "Migratie", vzmigrate: "Migratie", qmclone: "Klonen", vzclone: "Klonen",
  qmcreate: "Aanmaken", vzcreate: "Aanmaken", qmdestroy: "Verwijderen", vzdestroy: "Verwijderen", qmrestore: "Terugzetten", vzrestore: "Terugzetten",
  vncshell: "Shell", termproxy: "Shell", vncproxy: "Console", spiceproxy: "Console", aptupdate: "Pakketlijst bijwerken",
  imgcopy: "Schijf kopiëren", qmmove: "Schijf verplaatsen", move_volume: "Volume verplaatsen", srvreload: "Dienst herladen", srvrestart: "Dienst herstarten", startall: "Alles starten", stopall: "Alles stoppen",
};

/** Human description such as "CT 165 (controldeck) – Start"; unknown task types keep their Proxmox name. */
export function describeTask(task: Pick<ProxmoxTask, "type" | "target" | "targetType" | "targetName">): string {
  const action = labels[task.type] ?? task.type;
  if (!task.target) return action;
  const prefix = task.targetType === "lxc" ? "CT" : task.targetType === "qemu" ? "VM" : task.type.startsWith("vz") ? "CT" : task.type.startsWith("qm") ? "VM" : "";
  if (!prefix) return `${action} ${task.target}`;
  return `${prefix} ${task.target}${task.targetName ? ` (${task.targetName})` : ""} – ${action}`;
}

export function filterTasks(tasks: readonly ProxmoxTask[], filter: TaskFilter): ProxmoxTask[] {
  if (!Array.isArray(tasks)) throw new TypeError("Tasks must be a list");
  return tasks.filter(task => (!filter.node || task.node === filter.node) && (!filter.status || task.status === filter.status));
}

/** Duration in seconds as "45s", "3m 05s" or "2u 04m"; running tasks are measured until now. */
export function duration(start: number, end: number | null, now: number): string {
  const seconds = Math.max(0, Math.floor((end ?? now) - start));
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${String(seconds % 60).padStart(2, "0")}s`;
  return `${Math.floor(seconds / 3600)}u ${String(Math.floor(seconds / 60) % 60).padStart(2, "0")}m`;
}

/** Normalizes a pasted address such as https://192.168.1.98:8006/# for display before the server validates it. */
export function cleanAddress(value: string): string {
  return value.trim().replace(/#.*$/, "").replace(/\/+$/, "");
}

export type Counts = { ok: number; warning: number; error: number };
export type ClusterSummary = {
  guests: { id: number; name: string; node: string; type: "lxc" | "qemu"; cpu: number; cpus: number | null }[];
  nodesByCpu: { name: string; online: boolean; cpu: number; cpus: number | null }[];
  nodesByMemory: { name: string; memory: number; memoryUsed: number; memoryTotal: number }[];
  offlineNodes: string[];
  taskCategories: Record<string, Counts>;
  taskNodes: Record<string, Counts>;
  sdnZones: { available: number; error: number; pending: number; total: number };
  windowHours: number;
};

export const categoryLabels: Record<string, string> = {
  migration: "Migraties", vm: "Virtuele machines", container: "Containers", ceph: "Ceph", ha: "High availability", backup: "Backups", other: "Overig",
};

/** Bar width 0–100 and a load level; levels ≥ 90 % are flagged with text, not only colour. */
export function meter(value: number | null | undefined): { width: number; level: "normal" | "high" | "critical" | "unknown" } {
  if (typeof value !== "number" || !Number.isFinite(value)) return { width: 0, level: "unknown" };
  const width = Math.min(100, Math.max(0, value));
  return { width, level: width >= 90 ? "critical" : width >= 75 ? "high" : "normal" };
}

export function bytes(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) return "—";
  const units = ["B", "KiB", "MiB", "GiB", "TiB"];
  let index = 0, size = value;
  while (size >= 1024 && index < units.length - 1) { size /= 1024; index++; }
  return `${size >= 10 || index === 0 ? Math.round(size) : size.toFixed(1)} ${units[index]}`;
}

export type HealthLevel = "ok" | "warning" | "error" | "unknown";
export type MonitorNode = {
  name: string; overall: HealthLevel; stale: boolean; error?: string; updatedAt?: number; summary?: string | null;
  categories?: { id: string; status: HealthLevel; reason: string | null }[];
  temperature?: number | null; load?: number | null; hostUpdates?: number | null; powerWatts?: number | null;
  disks?: { name: string | null; model: string | null; health: string | null; smart: string | null; temperature: number | null; wear: number | null; reallocated: number | null; pending: number | null; standby: boolean; size: string | null }[];
  zfsPools?: { name: string | null; health: string | null; size: string | null; free: string | null }[];
  lxcUpdates?: { id: number | null; name: string | null; count: number | null; security: number | null; latest: string | null }[];
};

export const healthLabels: Record<string, string> = {
  cpu: "CPU", memory: "Geheugen", disks: "Schijven", storage: "Opslag", zfs_pool_capacity: "ZFS-capaciteit", pve_storage_capacity: "Proxmox-opslag",
  lxc_disk: "LXC-schijven", vm_disk: "VM-schijven", lxc_mounts: "LXC-mounts", remote_mounts: "Netwerkmounts", network: "Netwerk",
  services: "Services", vms: "Gasten", updates: "Updates", security: "Beveiliging", logs: "Logs",
};
export const healthText: Record<HealthLevel, string> = { ok: "✓ Gezond", warning: "△ Waarschuwing", error: "✗ Kritiek", unknown: "? Onbekend" };

/** Problems first (error, warning, unknown); healthy categories are only counted. */
export function healthProblems(categories: MonitorNode["categories"]): { problems: NonNullable<MonitorNode["categories"]>; healthy: number } {
  if (categories !== undefined && !Array.isArray(categories)) throw new TypeError("Categories must be a list");
  const rank: Record<HealthLevel, number> = { error: 0, warning: 1, unknown: 2, ok: 3 };
  const list = [...(categories ?? [])].sort((a, b) => rank[a.status] - rank[b.status] || a.id.localeCompare(b.id));
  return { problems: list.filter(item => item.status !== "ok"), healthy: list.filter(item => item.status === "ok").length };
}

/** Disk state: SMART failure, reallocated/pending sectors or ≥ 90 % wear are problems; unknown is never healthy. */
export function diskLevel(disk: NonNullable<MonitorNode["disks"]>[number]): HealthLevel {
  const smart = (disk.smart ?? "").toLowerCase(), health = (disk.health ?? "").toLowerCase();
  if (smart === "failed" || health === "critical" || health === "failed" || (disk.pending ?? 0) > 0) return "error";
  if ((disk.reallocated ?? 0) > 0 || (disk.wear ?? 0) >= 90 || health === "warning") return "warning";
  if (smart === "passed" || health === "healthy" || health === "ok") return "ok";
  return "unknown";
}
