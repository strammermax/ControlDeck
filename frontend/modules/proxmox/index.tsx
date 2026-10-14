"use client";
import {ProxmenuxHealth} from "../../components/proxmenux-health";
import {ProxmoxSummary} from "../../components/proxmox-summary";
import type {ModuleViewProps, ModuleSettingsProps} from "../contracts";
import {proxmoxView, proxmoxViews} from "./settings";

export function View({settings}:ModuleViewProps) {
  const view=proxmoxView(settings.view);
  return <div className="cd-proxmox-module"><p><a href="#proxmox">Open Proxmox →</a></p>{view === "health" ? <ProxmenuxHealth refreshSeconds={60} compact/> : <ProxmoxSummary refreshSeconds={60} view={view} embedded/>}</div>;
}
export function Settings({settings,onChange}:ModuleSettingsProps) {
  return <label>Weergave<select value={proxmoxView(settings.view)} onChange={event=>onChange({view:proxmoxView(event.target.value)})}>{Object.entries(proxmoxViews).map(([id,title])=><option key={id} value={id}>{title}</option>)}</select><small>Gebruikt je bestaande Proxmox-koppeling. Vernieuwt iedere minuut zolang de module zichtbaar is.</small></label>;
}
