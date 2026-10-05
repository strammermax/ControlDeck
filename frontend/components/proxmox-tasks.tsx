"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { describeTask, duration, filterTasks, type ProxmoxTask, type TaskFilter, type TaskStatus } from "../lib/proxmox";

type Response = { tasks: ProxmoxTask[]; updatedAt: number; stale: boolean; error?: string };
const statusText: Record<TaskStatus, string> = { running: "◌ Bezig", ok: "✓ OK", warning: "△ Waarschuwing", error: "✗ Fout" };
const time = (seconds: number) => new Date(seconds * 1000).toLocaleString("nl-NL", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit" });

/** Proxmox → Overzicht: recent tasks of every node in the cluster, read-only. */
export function ProxmoxTasks({ isAdmin, refreshSeconds }: { isAdmin: boolean; refreshSeconds: number }) {
  const [data, setData] = useState<Response | null>(null);
  const [error, setError] = useState("");
  const [notConnected, setNotConnected] = useState(false);
  const [filter, setFilter] = useState<TaskFilter>({ node: "", status: "" });
  const [open, setOpen] = useState<string | null>(null);
  const load = useCallback(async () => {
    try {
      const response = await fetch("/api/proxmox/tasks", { cache: "no-store" });
      const body = await response.json();
      if (response.status === 409 && body?.code === "not_connected") { setNotConnected(true); return; }
      if (!response.ok || !Array.isArray(body?.tasks)) throw new Error(typeof body?.error === "string" ? body.error : "Taken kunnen niet worden geladen.");
      setNotConnected(false); setData(body); setError("");
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Taken kunnen niet worden geladen."); }
  }, []);
  useEffect(() => {
    void load();
    const timer = setInterval(() => void load(), Math.max(15, refreshSeconds) * 1000);
    return () => clearInterval(timer);
  }, [load, refreshSeconds]);
  const nodes = useMemo(() => [...new Set((data?.tasks ?? []).map(task => task.node))].sort(), [data]);
  if (notConnected) return <div className="proxmox-empty"><p>Proxmox is nog niet gekoppeld.</p>{isAdmin ? <a className="provider-open" href="#admin/modules">Koppel Proxmox via Admin → Modules</a> : <p>Vraag een beheerder om Proxmox te koppelen.</p>}</div>;
  const now = Date.now() / 1000;
  const rows = data ? filterTasks(data.tasks, filter) : [];
  return <section className="proxmox-tasks">
    <div className="task-toolbar">
      <h3>Laatste gebeurtenissen</h3>
      <label>Node<select value={filter.node} onChange={event => setFilter({ ...filter, node: event.target.value })}><option value="">Alle nodes</option>{nodes.map(node => <option key={node}>{node}</option>)}</select></label>
      <label>Status<select value={filter.status} onChange={event => setFilter({ ...filter, status: event.target.value as TaskFilter["status"] })}><option value="">Alle</option><option value="error">Fout</option><option value="warning">Waarschuwing</option><option value="running">Bezig</option><option value="ok">OK</option></select></label>
      <span className="task-updated" role="status">{data ? `${data.stale ? "Verouderd · " : ""}bijgewerkt ${time(data.updatedAt)}` : error ? "" : "Laden…"}</span>
    </div>
    {(error || data?.stale) && <p className="config-error" role="alert">{error || data?.error}{data && " De laatst bekende gegevens blijven zichtbaar."}</p>}
    {data && (rows.length ? <div className="task-table"><table>
      <thead><tr><th>Status</th><th>Start</th><th>Duur</th><th>Node</th><th>Gebruiker</th><th>Beschrijving</th></tr></thead>
      <tbody>{rows.map(task => <tr key={task.id} className={`task-${task.status}`}>
        <td><span className={`task-status ${task.status}`}>{statusText[task.status]}</span></td>
        <td>{time(task.start)}</td><td>{duration(task.start, task.end, now)}</td><td>{task.node}</td><td>{task.user}</td>
        <td>{describeTask(task)}{task.message && open === task.id && <div className="task-message">{task.message}</div>}{task.message && <> <button type="button" className="task-more" aria-expanded={open === task.id} onClick={() => setOpen(open === task.id ? null : task.id)}>{open === task.id ? "verberg details" : "details"}</button></>}</td>
      </tr>)}</tbody>
    </table></div> : <p>Geen taken gevonden{filter.node || filter.status ? " voor dit filter" : ""}.</p>)}
  </section>;
}
