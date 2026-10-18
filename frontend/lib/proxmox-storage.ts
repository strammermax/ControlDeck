import type {GuestNode} from "./proxmox-guests";
export type StorageRow={key:string;name:string;node:string;type:string;shared:boolean;remote:boolean;category:"local"|"remote"|"unknown";status:"active"|"inactive";total:number|null;used:number|null;available:number|null};
export type StorageInventory={nodes:GuestNode[];storage:StorageRow[];identityComplete:boolean;updatedAt:number;stale:boolean};
export type PhysicalDisk={node:string;name:string;model:string|null;size:number|null;sizeLabel:string|null;health:string|null;smart:string|null;standby:boolean;temperature:number|null;wear:number|null;connection:string|null;rotation:number|null};
export type StoragePool={node:string;name:string;size:string|null;allocated:string|null;free:string|null;health:string|null};
export type StorageMount={node:string;source:string;target:string;type:string|null;scope:"host"|"container";container:string|null;reachable:boolean;readonly:boolean;managed:boolean;total:number|null;used:number|null;available:number|null};
export type StorageMonitorNode={name:string;loading?:boolean;error?:string;stale?:boolean;partial?:string[];updatedAt?:number;disks?:PhysicalDisk[];pools?:StoragePool[];mounts?:StorageMount[];disksAvailable?:boolean;mountsAvailable?:boolean};
const amount=(n:unknown)=>n===null||(typeof n==="number"&&Number.isFinite(n)&&n>=0&&n<=Number.MAX_SAFE_INTEGER);
const bounded=(v:unknown,max=512)=>typeof v==="string"&&v.length<=max&&!/[\x00-\x1f]/.test(v);
const host=(v:unknown)=>typeof v==="string"&&/^[A-Za-z0-9][A-Za-z0-9.-]{0,62}$/.test(v);
export function validateStorage(value:unknown):StorageInventory {
 const data=value as {storage?:StorageInventory;updatedAt?:number;stale?:boolean}|null,body=data?.storage;
 if(!body||!Array.isArray(body.storage)||body.storage.length>5000||!Array.isArray(body.nodes)||body.nodes.length>64||typeof body.identityComplete!=="boolean"||typeof data?.updatedAt!=="number"||!Number.isFinite(data.updatedAt)||data.updatedAt<0||typeof data.stale!=="boolean")throw new Error("Ongeldige opslaginventaris.");
 if(body.storage.some(r=>!r||!bounded(r.name,100)||!host(r.node)||!bounded(r.type,30)||! /^[a-f0-9]{24}$/.test(r.key)||!["local","remote","unknown"].includes(r.category)||!["active","inactive"].includes(r.status)||typeof r.shared!=="boolean"||typeof r.remote!=="boolean"||[r.total,r.used,r.available].some(n=>!amount(n))||(r.total!==null&&r.used!==null&&r.used>r.total)))throw new Error("Ongeldige opslagmetingen.");
 if(body.nodes.some(n=>!n||!host(n.name)||typeof n.online!=="boolean"))throw new Error("Ongeldige opslag-node.");
 if(new Set(body.storage.map(r=>`${r.node}:${r.name}`)).size!==body.storage.length||new Set(body.nodes.map(n=>n.name)).size!==body.nodes.length)throw new Error("Dubbele opslagidentiteit.");
 return {...body,updatedAt:data.updatedAt,stale:data.stale};
}
export function validateStorageMonitor(value:unknown):StorageMonitorNode[] {
 const rows=(value as {nodes?:unknown}|null)?.nodes;
 if(!Array.isArray(rows)||rows.length>64)throw new Error("Ongeldige opslagmonitor.");
 for(const n of rows){
  if(!n||!host(n.name)||["disks","pools","mounts"].some(k=>n[k]!==undefined&&(!Array.isArray(n[k])||n[k].length>1000)))throw new Error("Ongeldige opslagmonitor.");
  if(n.disks?.some((d:PhysicalDisk)=>!d||d.node!==n.name||!bounded(d.name,80)||[d.size,d.temperature,d.wear,d.rotation].some(v=>!amount(v))||typeof d.standby!=="boolean"))throw new Error("Ongeldige schijfmeting.");
  if(n.pools?.some((p:StoragePool)=>!p||p.node!==n.name||!bounded(p.name,100)))throw new Error("Ongeldige pool.");
  if(n.mounts?.some((m:StorageMount)=>!m||m.node!==n.name||!bounded(m.source)||!bounded(m.target)||!['host','container'].includes(m.scope)||[m.total,m.used,m.available].some(v=>!amount(v))||[m.reachable,m.readonly,m.managed].some(v=>typeof v!=="boolean")))throw new Error("Ongeldige mountmeting.");
 }
 if(new Set(rows.map(n=>n.name)).size!==rows.length)throw new Error("Dubbele monitornode.");
 return rows;
}
export type StorageGroup=StorageRow&{names:string[];nodes:string[];unavailableNodes:string[]};
export function storageMonitorSelection(monitor:StorageMonitorNode[],nodes:GuestNode[]) {
 return monitor.filter(n=>nodes.some(node=>node.name===n.name));
}
export function storageSelection(data:StorageInventory,scope="cluster") {
 const rows=data.storage.filter(r=>scope==="cluster"||r.node===scope),groups=new Map<string,StorageRow[]>();
 for(const row of rows)groups.set(row.key,[...(groups.get(row.key)??[]),row]);
 const storage:StorageGroup[]=[...groups.values()].map(members=>{
  const row=members.find(r=>r.status==="active"&&r.total!==null)??members.find(r=>r.status==="active")??members[0];
  return {...row,names:[...new Set(members.map(r=>r.name))],nodes:[...new Set(members.map(r=>r.node))].sort(),unavailableNodes:[...new Set(members.filter(r=>r.status!=="active").map(r=>r.node))]};
 });
 return {storage,nodes:data.nodes.filter(n=>scope==="cluster"||n.name===scope)};
}
export function storageTotals(rows:StorageGroup[]) {
 const category=(name:string)=>{
  const relevant=rows.filter(r=>r.category===name&&r.status==="active"),known=relevant.filter(r=>r.total!==null&&r.used!==null&&r.available!==null);
  const add=(key:"used"|"total"|"available")=>relevant.length&&!known.length?null:known.reduce((a,r)=>a+(r[key]??0),0);
  return {used:add("used"),total:add("total"),available:add("available"),incomplete:known.length!==relevant.length};
 };
 return {local:category("local"),remote:category("remote")};
}
export function diskHealth(disk:PhysicalDisk):"ok"|"warning"|"error"|"unknown" {
 const health=`${disk.health??""} ${disk.smart??""}`.toLowerCase();
 if(/critical|fail|bad|unhealthy|error/.test(health))return "error";
 if(/warn|degrad/.test(health))return "warning";
 return /\b(healthy|passed|ok)\b/.test(health)?"ok":"unknown";
}
export function diskKind(disk:PhysicalDisk) {return disk.connection==="usb"?"USB":disk.name.startsWith("nvme")?"NVMe":disk.rotation===0?"SSD":disk.rotation!==null&&disk.rotation>0?"HDD":"Disk";}
