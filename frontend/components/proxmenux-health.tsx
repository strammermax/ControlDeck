"use client";
import { useCallback, useEffect, useState } from "react";
import { collectUpdates, diskStatus, healthLabels, healthProblems, healthText, type MonitorNode } from "../lib/proxmox";

const levelSymbol = { ok: "✓", warning: "△", error: "✗", unknown: "?", standby: "◌" } as const;
const diskText = { ok: "OK", warning: "Let op", error: "Fout", unknown: "Onbekend", standby: "Slaapstand" } as const;

/** Node health from ProxMenux Monitor: overall state, temperature, CPU power, disks, ZFS and LXC updates. */
export function ProxmenuxHealth({ refreshSeconds }: { refreshSeconds: number }) {
  const [nodes, setNodes] = useState<MonitorNode[] | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try {
      const response = await fetch("/api/proxmenux/summary", { cache: "no-store" });
      const body = await response.json();
      if (response.status === 409) { setNodes(null); setError(""); return; }
      if (!response.ok || !Array.isArray(body?.nodes)) throw new Error(typeof body?.error === "string" ? body.error : "Nodegezondheid kan niet worden geladen.");
      // Alphabetical, so cards do not jump around between refreshes.
      setNodes([...body.nodes].sort((a: MonitorNode, b: MonitorNode) => a.name.localeCompare(b.name))); setError("");
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Nodegezondheid kan niet worden geladen."); }
  }, []);
  const loading = nodes?.some(node => node.loading) ?? false;
  useEffect(() => {
    void load();
    // While a node is still loading in the background, check back sooner.
    const timer = setInterval(() => void load(), (loading ? 5 : Math.max(15, refreshSeconds)) * 1000);
    return () => clearInterval(timer);
  }, [load, refreshSeconds, loading]);
  if (!nodes) return error ? <p className="config-error" role="alert">{error}</p> : null;
  const disks = nodes.flatMap(node => (node.disks ?? []).map(disk => ({ node: node.name, ...disk })));
  const pools = nodes.flatMap(node => (node.zfsPools ?? []).map(pool => ({ node: node.name, ...pool })));
  const updates = collectUpdates(nodes.filter(node => !node.loading));
  return <section className="node-health" aria-label="Nodegezondheid">
    <div className="health-grid">
      {nodes.map(node => {
        const { problems, healthy } = healthProblems(node.categories);
        return <article key={node.name} className={`widget health-card ${node.overall}`}>
          <header><h3>{node.name}</h3><span className={`task-status ${node.overall === "unknown" ? "" : node.overall}`}>{node.loading ? "◌ Laden…" : healthText[node.overall]}</span></header>
          {node.loading && <p className="health-ok" role="status">Gegevens worden opgehaald. Dit kan bij kleinere nodes even duren.</p>}
          {node.error && <p className="health-error" role="alert">{node.error}{node.updatedAt ? " · laatst bekende gegevens" : ""}</p>}
          {node.partial && node.partial.length > 0 && <p className="health-error" role="status">Niet beschikbaar: {node.partial.join(", ")}. De overige gegevens zijn actueel.</p>}
          {node.updatedAt !== undefined && <dl className="health-stats">
            <div><dt>Temperatuur</dt><dd>{node.temperature != null ? `${node.temperature.toFixed(0)} °C` : "—"}</dd></div>
            <div title={node.powerSource ? `Bron: ${node.powerSource}. Alleen de CPU, niet het totale verbruik van de server.` : undefined}><dt>CPU-vermogen</dt><dd>{node.powerWatts != null ? `${node.powerWatts.toFixed(0)} W` : "—"}</dd></div>
            <div title="Gemiddelde load over 1 minuut, ten opzichte van het aantal CPU-threads"><dt>Load</dt><dd>{node.load != null ? node.load.toFixed(2) : "—"}{node.threads ? <small> / {node.threads}</small> : null}</dd></div>
            <div><dt>Host-updates</dt><dd>{node.hostUpdates ?? "—"}</dd></div>
          </dl>}
          {problems.length > 0 && <ul className="health-problems">{problems.map(item => <li key={item.id} className={item.status}>
            <span aria-hidden="true">{levelSymbol[item.status]}</span> <strong>{healthLabels[item.id] ?? item.id}</strong>{item.reason && <span> — {item.reason}</span>}
          </li>)}</ul>}
          {node.updatedAt !== undefined && node.categories && node.categories.length > 0 && <p className="health-ok">{healthy} {healthy === 1 ? "controle" : "controles"} in orde{node.stale ? " · verouderd" : ""}</p>}
        </article>;
      })}
    </div>
    <div className="widget-grid two">
      <article className="widget">
        <h3>Schijven <small>SMART, temperatuur en slijtage · slapende schijven worden niet gewekt</small></h3>
        {disks.length ? <div className="task-table plain"><table>
          <thead><tr><th>Status</th><th>Node</th><th>Schijf</th><th>Temp.</th><th>Slijtage</th></tr></thead>
          <tbody>{disks.map(disk => { const level = diskStatus(disk); return <tr key={`${disk.node}-${disk.name}`}>
            <td><span className={`task-status ${level === "unknown" || level === "standby" ? "" : level}`}>{levelSymbol[level]} {diskText[level]}</span></td>
            <td>{disk.node}</td><td title={disk.model ?? undefined}>{disk.name}{disk.size ? ` · ${disk.size}` : ""}</td>
            <td>{disk.temperature != null ? `${disk.temperature} °C` : "—"}</td><td>{disk.wear != null ? `${disk.wear} %` : "—"}</td>
          </tr>; })}</tbody></table></div> : <p>{loading ? "Schijfgegevens worden opgehaald…" : "Geen schijfgegevens."}</p>}
        {pools.length > 0 && <><h4>ZFS-pools</h4><ul className="pool-list">{pools.map(pool => <li key={`${pool.node}-${pool.name}`}>
          <span className={`task-status ${pool.health === "ONLINE" ? "ok" : "error"}`}>{pool.health === "ONLINE" ? "✓" : "✗"} {pool.health ?? "?"}</span> {pool.node} · {pool.name} · {pool.free} vrij van {pool.size}
        </li>)}</ul></>}
      </article>
      <article className="widget">
        <h3>LXC-updates <small>{updates.containers ? `${updates.containers} ${updates.containers === 1 ? "container" : "containers"} · ${updates.security} beveiligingsupdates · beveiliging eerst` : "via Helper-Scripts"}</small></h3>
        {updates.rows.length ? <ul className="pool-list">{updates.rows.map(update => <li key={`${update.node}-${update.id}`}>
          <span className={`task-status ${update.security ? "warning" : ""}`}>{update.security ? `△ ${update.security} beveiliging` : "↑"}</span> CT {update.id} ({update.name}) · {update.node} · {update.count ?? "?"} {update.count === 1 ? "update" : "updates"}
          {update.packages.length > 0 && <div className="update-packages">{update.packages.join(", ")}{(update.count ?? 0) > update.packages.length ? " …" : ""}</div>}
        </li>)}</ul> : updates.missing.length === 0 && !loading ? <p>✓ Alle containers zijn bijgewerkt.</p> : null}
        {updates.missing.length > 0 && <p className="health-error" role="status">Geen updategegevens van {updates.missing.join(", ")}; die containers ontbreken in deze lijst.</p>}
        {loading && <p className="health-ok" role="status">Nog niet alle nodes zijn geladen.</p>}
      </article>
    </div>
  </section>;
}
