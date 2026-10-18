"use client";
import type {ReactNode} from "react";
import {EditableGrid} from "./editable-grid";
import {LayoutToolbar, usePageLayout} from "./page-layout";
import {ProxmenuxHealth} from "./proxmenux-health";
import {ProxmoxTasks} from "./proxmox-tasks";
import {proxmoxSummaryWidgets, useProxmoxSummary} from "./proxmox-summary";
import {proxmoxPageCells, proxmoxPageGrid, proxmoxWidgetSizes} from "../lib/proxmox-layout";
import {groupCells, withGroupCells} from "../lib/page-layouts";

const titles: Record<string, string> = {health: "ProxMenux-gezondheid", guests: "Gasten", "nodes-cpu": "Nodes · CPU", "nodes-memory": "Nodes · geheugen", "task-categories": "Taken per categorie", "task-nodes": "Taken per node", sdn: "SDN-zones", tasks: "Takenlijst"};

/** Proxmox overview with a personal layout: every widget can be moved and resized. */
export function ProxmoxPage({csrfToken, isAdmin, refreshSeconds}: {csrfToken: string; isAdmin: boolean; refreshSeconds: number}) {
  const {data, error} = useProxmoxSummary(refreshSeconds);
  const layout = usePageLayout("proxmox", csrfToken);
  const widgets = new Map<string, ReactNode>([["health", <ProxmenuxHealth refreshSeconds={refreshSeconds}/>]]);
  for (const widget of data ? proxmoxSummaryWidgets(data.summary) : []) widgets.set(widget.id, <article className="widget">{widget.node}</article>);
  widgets.set("tasks", <ProxmoxTasks isAdmin={isAdmin} refreshSeconds={refreshSeconds}/>);
  const ids = Object.keys(proxmoxWidgetSizes).filter(id => widgets.has(id));
  const cells = proxmoxPageCells(ids, layout.cells);
  return <section className="cd-proxmox-page cluster-summary" aria-label="Proxmox-overzicht">
    <LayoutToolbar editing={layout.editing} busy={layout.busy} error={layout.error} onEdit={() => layout.edit(cells)} onSave={() => void layout.save(cells)} onCancel={layout.cancel} onReset={() => void layout.reset()}/>
    {(error || data?.stale) && <p className="config-error" role="alert">{error || data?.error} De laatst bekende gegevens blijven zichtbaar.</p>}
    {data && data.summary.offlineNodes.length > 0 && <p className="config-error" role="alert">✗ Offline: {data.summary.offlineNodes.join(", ")}</p>}
    <EditableGrid cells={groupCells(cells, "main")} bounds={proxmoxPageGrid} editing={layout.editing}
      onChange={next => layout.change(withGroupCells(cells, "main", next))} label={id => titles[id] ?? id} render={id => widgets.get(id)}/>
  </section>;
}
