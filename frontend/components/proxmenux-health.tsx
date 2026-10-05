"use client";
import { useCallback, useEffect, useState } from "react";
import { diskLevel, healthLabels, healthProblems, healthText, type MonitorNode } from "../lib/proxmox";

const levelSymbol = { ok: "✓", warning: "△", error: "✗", unknown: "?" } as const;

/** Node health from ProxMenux Monitor: overall state, temperature, power, disks, ZFS and LXC updates. */
export function ProxmenuxHealth({ refreshSeconds }: { refreshSeconds: number }) {
  const [nodes, setNodes] = useState<MonitorNode[] | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try {
      const response = await fetch("/api/proxmenux/summary", { cache: "no-store" });
      const body = await response.json();
      if (response.status === 409) { setNodes(null); setError(""); return; }
      if (!response.ok || !Array.isArray(body?.nodes)) throw new Error(typeof body?.error === "string" ? body.error : "Nodegezondheid kan niet worden geladen.");
      setNodes(body.nodes); setError("");
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Nodegezondheid kan niet worden geladen."); }
  }, []);
  useEffect(() => {
    void load();
    const timer = setInterval(() => void load(), Math.max(15, refreshSeconds) * 1000);
    return () => clearInterval(timer);
  }, [load, refreshSeconds]);
  if (!nodes) return error ? <p className="config-error" role="alert">{error}</p> : null;
  const disks = nodes.flatMap(node => (node.disks ?? []).map(disk => ({ node: node.name, ...disk })));
  const pools = nodes.flatMap(node => (node.zfsPools ?? []).map(pool => ({ node: node.name, ...pool })));
  const updates = nodes.flatMap(node => (node.lxcUpdates ?? []).map(update => ({ node: node.name, ...update })));
  return <section className="node-health" aria-label="Nodegezondheid">
    <div className="health-grid">
      {nodes.map(node => {
        const { problems, healthy } = healthProblems(node.categories);
        return <article key={node.name} className={`widget health-card ${node.overall}`}>
          <header><h3>{node.name}</h3><span className={`task-status ${node.overall === "unknown" ? "" : node.overall}`}>{healthText[node.overall]}</span></header>
          {node.error && <p className="health-error" role="alert">{node.error}{node.updatedAt ? " · laatst bekende gegevens" : ""}</p>}
          {node.updatedAt !== undefined && <dl className="health-stats">
            <div><dt>Temperatuur</dt><dd>{node.temperature != null ? `${node.temperature.toFixed(0)} °C` : "—"}</dd></div>
            <div><dt>Verbruik</dt><dd>{node.powerWatts != null ? `${node.powerWatts.toFixed(0)} W` : "—"}</dd></div>
            <div><dt>Load</dt><dd>{node.load != null ? node.load.toFixed(2) : "—"}</dd></div>
            <div><dt>Host-updates</dt><dd>{node.hostUpdates ?? "—"}</dd></div>
          </dl>}
          {problems.length > 0 && <ul className="health-problems">{problems.map(item => <li key={item.id} className={item.status}>
            <span aria-hidden="true">{levelSymbol[item.status]}</span> <strong>{healthLabels[item.id] ?? item.id}</strong>{item.reason && <span> — {item.reason}</span>}
          </li>)}</ul>}
          {node.updatedAt !== undefined && <p className="health-ok">{healthy} {healthy === 1 ? "controle" : "controles"} in orde{node.stale ? " · verouderd" : ""}</p>}
        </article>;
      })}
    </div>
    <div className="widget-grid two">
      <article className="widget">
        <h3>Schijven <small>SMART, temperatuur en slijtage</small></h3>
        {disks.length ? <div className="task-table plain"><table>
          <thead><tr><th>Status</th><th>Node</th><th>Schijf</th><th>Temp.</th><th>Slijtage</th></tr></thead>
          <tbody>{disks.map(disk => { const level = diskLevel(disk); return <tr key={`${disk.node}-${disk.name}`}>
            <td><span className={`task-status ${level === "unknown" ? "" : level}`}>{levelSymbol[level]} {level === "ok" ? "OK" : level === "warning" ? "Let op" : level === "error" ? "Fout" : "Onbekend"}</span></td>
            <td>{disk.node}</td><td title={disk.model ?? undefined}>{disk.name}{disk.size ? ` · ${disk.size}` : ""}{disk.standby ? " · slaapstand" : ""}</td>
            <td>{disk.temperature != null ? `${disk.temperature} °C` : "—"}</td><td>{disk.wear != null ? `${disk.wear} %` : "—"}</td>
          </tr>; })}</tbody></table></div> : <p>Geen schijfgegevens.</p>}
        {pools.length > 0 && <><h4>ZFS-pools</h4><ul className="pool-list">{pools.map(pool => <li key={`${pool.node}-${pool.name}`}>
          <span className={`task-status ${pool.health === "ONLINE" ? "ok" : "error"}`}>{pool.health === "ONLINE" ? "✓" : "✗"} {pool.health ?? "?"}</span> {pool.node} · {pool.name} · {pool.free} vrij van {pool.size}
        </li>)}</ul></>}
      </article>
      <article className="widget">
        <h3>LXC-updates <small>via Helper-Scripts, beveiligingsupdates eerst</small></h3>
        {updates.length ? <ul className="pool-list">{updates.map(update => <li key={`${update.node}-${update.id}`}>
          <span className={`task-status ${update.security ? "warning" : ""}`}>{update.security ? `△ ${update.security} beveiliging` : "↑"}</span> CT {update.id} ({update.name}) · {update.node} · {update.count ?? "?"} {update.count === 1 ? "update" : "updates"}{update.latest ? ` → ${update.latest}` : ""}
        </li>)}</ul> : <p>✓ Alle containers zijn bijgewerkt.</p>}
      </article>
    </div>
  </section>;
}
