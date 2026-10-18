/**
 * Adapted from MacRimi/ProxMenux VirtualMachines (GPL-3.0), commit
 * d4e98d16b11733e518b0162db1b528b2ecd4cc53. Original overview/list structure,
 * donut geometry, metric layout and palette retained; see /proxmenux/NOTICE.txt.
 */
import type {ReactNode} from "react";
import {guestBytes,guestGB,guestPercent,guestTotals,guestUptime,type Guest,type GuestNode} from "../../lib/proxmox-guests";
import {parseTags,tagToColor} from "./pve-tag-color";

export function GuestIcon({kind="server"}:{kind?:string}) {
 return <svg className="pm-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">{kind==="activity"?<path d="M22 12h-4l-3 9-6-18-3 9H2"/>:kind==="running"?<path d="m7 4 13 8-13 8Z"/>:kind==="stopped"?<rect x="5" y="5" width="14" height="14" rx="1"/>:kind==="network"?<><path d="M12 8v8M5 16v-4h14v4"/><rect x="9" y="2" width="6" height="6"/><rect x="2" y="16" width="6" height="6"/><rect x="16" y="16" width="6" height="6"/></>:kind==="cpu"?<><rect x="6" y="6" width="12" height="12" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 2v4m6-4v4M9 18v4m6-4v4M2 9h4m-4 6h4m12-6h4m-4 6h4"/></>:kind==="memory"?<><rect x="3" y="6" width="18" height="11" rx="1"/><path d="M6 10h3m3 0h3m3 0h1M6 17v3m4-3v3m4-3v3m4-3v3"/></>:kind==="disk"?<><path d="m5 5-3 10v5h20v-5L19 5ZM2 15h20M6 18h1m3 0h1"/></>:kind==="lxc"?<><path d="m12 2 9 5v10l-9 5-9-5V7Zm0 10 9-5M12 12 3 7m9 5v10"/></>:<><rect x="3" y="3" width="18" height="7" rx="2"/><rect x="3" y="14" width="18" height="7" rx="2"/><path d="M7 6h.01M7 17h.01"/></>}</svg>;
}
const usageColor=(percent:number|null)=>percent!==null&&percent>=90?"#ef4444":percent!==null&&percent>=75?"#f59e0b":"#3b82f6";
const pct=(value:number|null)=>value===null?"—":`${Math.round(value)}%`;
export function Bar({value,color}:{value:number|null;color?:string}) {
 return <div className="pm-progress" aria-hidden="true"><div style={{width:`${Math.max(0,Math.min(100,value??0))}%`,background:color??usageColor(value)}}/></div>;
}
export function Donut({value,color}:{value:number|null;color?:string}) {
 return <svg viewBox="0 0 36 36" className="pm-donut" aria-label={pct(value)}>
  <circle cx="18" cy="18" r="15.9155" fill="none" stroke="rgba(99,102,241,0.15)" strokeWidth="3"/>
  <circle cx="18" cy="18" r="15.9155" fill="none" stroke={color??usageColor(value)} strokeWidth="3" strokeDasharray={`${Math.max(0,Math.min(100,value??0))} 100`} strokeLinecap="round" style={{transform:"rotate(-90deg)",transformOrigin:"50% 50%"}}/>
  <text x="18" y="19.5" textAnchor="middle" fontSize="10" fontWeight="700" fill="currentColor">{pct(value)}</text>
 </svg>;
}
export function Card({title,icon,children}:{title:string;icon:string;children:ReactNode}) {
 return <article className="pm-card"><header className="pm-card-head"><h3>{title}</h3><GuestIcon kind={icon}/></header><div className="pm-card-content">{children}</div></article>;
}
export function Pair({label,children}:{label:string;children:ReactNode}) {return <div className="pm-pair"><span>{label}</span><strong>{children}</strong></div>;}
export function GuestOverview({guests,nodes}:{guests:Guest[];nodes:GuestNode[]}) {
 const total=guestTotals(guests,nodes),running=guests.filter(vm=>vm.status==="running").length,stopped=guests.filter(vm=>vm.status==="stopped").length;
 const vms=guests.filter(vm=>vm.type==="qemu").length,lxc=guests.filter(vm=>vm.type==="lxc").length;
 const diskPercent=guestPercent(total.diskUsed,total.diskTotal),memoryAlloc=guestPercent(total.allocatedMemory,total.memoryTotal);
 return <div className="pm-overview">
  <Card title="Total VMs & LXCs" icon="server"><div className="pm-headline"><div><b>{running}</b><span>/ {guests.length}</span></div><span className="pm-badge pm-green">{running} running</span></div><div className="pm-pills">{vms>0&&<span className="pm-badge pm-green">{vms} VMs</span>}{lxc>0&&<span className="pm-badge pm-blue">{lxc} LXC</span>}{stopped>0&&<span className="pm-badge">{stopped} stopped</span>}</div></Card>
  <Card title="Total CPU Allocated" icon="cpu"><div className="pm-donut-row"><Donut value={total.cpuPercent}/><div className="pm-summary-metrics"><div><Pair label="Used">{pct(total.cpuPercent)}</Pair><Bar value={total.cpuPercent}/></div><Pair label="Configured">{total.configured??"—"} / {total.cpuTotal??"—"} vCPU</Pair><Pair label="In use">{total.inUse} / {total.cpuTotal??"—"} vCPU</Pair></div></div></Card>
  <Card title="Total Memory" icon="memory"><div className="pm-donut-row"><Donut value={total.memoryPercent}/><div className="pm-summary-metrics"><div><Pair label="Used">{guestGB(total.memoryUsed)}</Pair><Bar value={total.memoryPercent}/></div><div><Pair label="Alloc">{guestGB(total.allocatedMemory)}</Pair><Bar value={memoryAlloc} color={memoryAlloc!==null&&memoryAlloc>100?"#f59e0b":"rgba(99,102,241,.55)"}/></div><Pair label="Total">{guestGB(total.memoryTotal,0)} GB</Pair></div></div></Card>
  <Card title="Total Disk" icon="disk"><div className="pm-disk-head"><div><strong>{guestBytes(total.diskUsed)}</strong> <span>used</span></div><span className="pm-badge">{pct(diskPercent)} util</span></div><div className="pm-disk-bar"><div style={{width:`${Math.max(0,Math.min(100,diskPercent??0))}%`,background:usageColor(diskPercent)}}/><div/></div><div className="pm-disk-legend"><span><i/>Used {guestBytes(total.diskUsed)}</span><span><i/>Alloc {guestBytes(total.diskTotal)}</span></div></Card>
 </div>;
}
function Metric({label,value,percent}:{label:string;value:string;percent:number|null}) {return <div className="pm-guest-metric"><small>{label}</small><strong>{value}</strong><Bar value={percent}/></div>;}
export function GuestCard({guest:vm}:{guest:Guest}) {
 const cpu=vm.cpu===null?null:vm.cpu*100,mem=guestPercent(vm.mem,vm.maxmem),disk=guestPercent(vm.disk,vm.maxdisk);
 return <article className="pm-guest" aria-label={`${vm.name} · ${vm.node} · ${vm.vmid}`}>
  <header className="pm-guest-head"><span className={`pm-badge ${vm.status==="running"?"pm-green":vm.status==="stopped"?"pm-red":""}`}><GuestIcon kind={vm.status}/>{vm.status.toUpperCase()}</span><span className={`pm-badge ${vm.type==="lxc"?"pm-cyan":"pm-purple"}`}><GuestIcon kind={vm.type==="lxc"?"lxc":"server"}/>{vm.type==="lxc"?"LXC":"VM"}</span><strong>{vm.name}</strong><span className="pm-muted">ID: {vm.vmid}</span>{parseTags(vm.tags).map(tag=><span key={tag} className="pm-tag" style={{background:tagToColor(tag).bg}} title={tag}/>)}<span className="pm-node-name">{vm.node}</span>{vm.updates!==null&&vm.updates>0&&<span className="pm-badge pm-purple pm-update" title="Beschikbare pakketupdates">↑ {vm.updates}</span>}</header>
  <div className="pm-guest-body"><div className="pm-guest-identity">{vm.status==="running"&&<><span>Uptime: {guestUptime(vm.uptime)}</span>{vm.ip&&<span><GuestIcon kind="network"/>{vm.ip}</span>}</>}</div><div className="pm-guest-metrics">
   <Metric label="CPU Usage" value={cpu===null?"—":`${cpu.toFixed(1)}%`} percent={cpu}/><Metric label="Memory" value={`${guestGB(vm.mem)} / ${guestGB(vm.maxmem)} GB`} percent={mem}/><Metric label="Disk Usage" value={`${guestGB(vm.disk)} / ${guestGB(vm.maxdisk)} GB`} percent={disk}/>
   <div className="pm-io"><small>Disk I/O</small><span className="pm-green-text"><GuestIcon kind="disk"/>↓ {guestBytes(vm.diskread)}</span><span className="pm-blue-text"><GuestIcon kind="disk"/>↑ {guestBytes(vm.diskwrite)}</span></div><div className="pm-io"><small>Network I/O</small><span className="pm-green-text"><GuestIcon kind="network"/>↓ {guestBytes(vm.netin)}</span><span className="pm-blue-text"><GuestIcon kind="network"/>↑ {guestBytes(vm.netout)}</span></div>
  </div></div>
 </article>;
}
