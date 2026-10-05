"use client";
import { useCallback, useEffect, useState } from "react";
import { bytes, categoryLabels, meter, type ClusterSummary, type Counts } from "../lib/proxmox";

type Response = { summary: ClusterSummary; updatedAt: number; stale: boolean; error?: string };

function Meter({ label, value, detail }: { label: string; value: number; detail: string }) {
  const { width, level } = meter(value);
  return <li className="meter-row" title={`${label}: ${value.toFixed(1)} % · ${detail}`}>
    <span className="meter-label">{label}</span>
    <span className="meter-track" aria-hidden="true"><span className={`meter-fill ${level}`} style={{ width: `${width}%` }}/></span>
    <span className="meter-value">{level === "critical" ? "△ " : ""}{value.toFixed(1)} %</span>
  </li>;
}

function CountCells({ counts }: { counts: Counts }) {
  return <>
    <td className={counts.error ? "count error" : "count none"}><span aria-hidden="true">✗</span> {counts.error}<span className="sr-only"> fout</span></td>
    <td className={counts.warning ? "count warning" : "count none"}><span aria-hidden="true">△</span> {counts.warning}<span className="sr-only"> waarschuwing</span></td>
    <td className={counts.ok ? "count ok" : "count none"}><span aria-hidden="true">✓</span> {counts.ok}<span className="sr-only"> OK</span></td>
  </>;
}

/** Cluster widgets above the task list: busiest guests and nodes, task counts and SDN zones. */
export function ProxmoxSummary({ refreshSeconds }: { refreshSeconds: number }) {
  const [data, setData] = useState<Response | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try {
      const response = await fetch("/api/proxmox/summary", { cache: "no-store" });
      const body = await response.json();
      if (response.status === 409) { setData(null); setError(""); return; }
      if (!response.ok || !body?.summary) throw new Error(typeof body?.error === "string" ? body.error : "Clusteroverzicht kan niet worden geladen.");
      setData(body); setError("");
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Clusteroverzicht kan niet worden geladen."); }
  }, []);
  useEffect(() => {
    void load();
    const timer = setInterval(() => void load(), Math.max(15, refreshSeconds) * 1000);
    return () => clearInterval(timer);
  }, [load, refreshSeconds]);
  if (!data) return error ? <p className="config-error" role="alert">{error}</p> : null;
  const summary = data.summary;
  return <section className="cluster-summary" aria-label="Clusteroverzicht">
    {(error || data.stale) && <p className="config-error" role="alert">{error || data.error} De laatst bekende gegevens blijven zichtbaar.</p>}
    {summary.offlineNodes.length > 0 && <p className="config-error" role="alert">✗ Offline: {summary.offlineNodes.join(", ")}</p>}
    <div className="widget-grid">
      <article className="widget">
        <h3>Gasten met het hoogste CPU-gebruik</h3>
        {summary.guests.length ? <ul className="meters">{summary.guests.map(guest => <Meter key={guest.id} label={`${guest.name} (${guest.id}) · ${guest.node}`} value={guest.cpu} detail={`${guest.type === "lxc" ? "container" : "VM"}, ${guest.cpus ?? "?"} CPU`}/>)}</ul> : <p>Geen draaiende gasten.</p>}
      </article>
      <article className="widget">
        <h3>Nodes · CPU</h3>
        <ul className="meters">{summary.nodesByCpu.map(node => <Meter key={node.name} label={node.name} value={node.cpu} detail={`${node.cpus ?? "?"} CPU`}/>)}</ul>
      </article>
      <article className="widget">
        <h3>Nodes · geheugen</h3>
        <ul className="meters">{summary.nodesByMemory.map(node => <Meter key={node.name} label={node.name} value={node.memory} detail={`${bytes(node.memoryUsed)} van ${bytes(node.memoryTotal)}`}/>)}</ul>
      </article>
      <article className="widget">
        <h3>Taken per categorie <small>laatste {summary.windowHours} u</small></h3>
        <table className="count-table"><thead><tr><th>Categorie</th><th>Fout</th><th>Waarsch.</th><th>OK</th></tr></thead>
          <tbody>{Object.entries(summary.taskCategories).filter(([name, counts]) => name !== "other" || counts.ok + counts.warning + counts.error > 0).map(([name, counts]) => <tr key={name}><td>{categoryLabels[name] ?? name}</td><CountCells counts={counts}/></tr>)}</tbody></table>
      </article>
      <article className="widget">
        <h3>Taken per node <small>laatste {summary.windowHours} u, meeste fouten eerst</small></h3>
        <table className="count-table"><thead><tr><th>Node</th><th>Fout</th><th>Waarsch.</th><th>OK</th></tr></thead>
          <tbody>{Object.entries(summary.taskNodes).map(([name, counts]) => <tr key={name}><td>{name}</td><CountCells counts={counts}/></tr>)}</tbody></table>
      </article>
      <article className="widget">
        <h3>SDN-zones</h3>
        {summary.sdnZones.total ? <table className="count-table"><tbody>
          <tr><td><span className="count ok">✓</span> Beschikbaar</td><td>{summary.sdnZones.available}</td></tr>
          <tr><td><span className={summary.sdnZones.error ? "count error" : "count none"}>✗</span> Fout</td><td>{summary.sdnZones.error}</td></tr>
          <tr><td><span className="count none">◌</span> In behandeling</td><td>{summary.sdnZones.pending}</td></tr>
          <tr><td>Totaal</td><td>{summary.sdnZones.total}</td></tr>
        </tbody></table> : <p>Geen SDN-zones ingericht.</p>}
      </article>
    </div>
  </section>;
}
