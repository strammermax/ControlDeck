/** Read-only cluster inventory; monitor details enrich only the canonical node/guest pair. */
export type Guest = {vmid:number;node:string;name:string;type:"qemu"|"lxc";status:string;tags:string;ip:string|null;updates:number|null;cpu:number|null;maxcpu:number|null;mem:number|null;maxmem:number|null;disk:number|null;maxdisk:number|null;uptime:number|null;netin:number|null;netout:number|null;diskread:number|null;diskwrite:number|null};
export type GuestNode = {name:string;online:boolean;cpu:number|null;maxcpu:number|null;mem:number|null;maxmem:number|null};
export type GuestInventory = {guests:Guest[];nodes:GuestNode[];updatedAt:number;stale:boolean};
const metrics=["cpu","maxcpu","mem","maxmem","disk","maxdisk","uptime","netin","netout","diskread","diskwrite","updates"] as const;
export function validateInventory(value:unknown):GuestInventory {
 const data=value as {inventory?:GuestInventory;updatedAt?:number;stale?:boolean}|null;
 const inv=data?.inventory;
 if(!inv||!Array.isArray(inv.guests)||inv.guests.length>5000||!Array.isArray(inv.nodes)||inv.nodes.length>64||typeof data?.updatedAt!=="number"||!Number.isFinite(data.updatedAt)||data.updatedAt<0||data.updatedAt>1e11||typeof data.stale!=="boolean")throw new Error("Ongeldige clustergegevens.");
 const nonnegative=(n:unknown)=>n===null||(typeof n==="number"&&Number.isFinite(n)&&n>=0&&n<=Number.MAX_SAFE_INTEGER);
 const host=(s:unknown)=>typeof s==="string"&&/^[A-Za-z0-9][A-Za-z0-9.-]{0,62}$/.test(s);
 if(inv.guests.some(g=>!g||!Number.isSafeInteger(g.vmid)||g.vmid<1||!host(g.node)||typeof g.name!=="string"||g.name.length>100||!["qemu","lxc"].includes(g.type)||!["running","stopped","paused","unknown"].includes(g.status)||typeof g.tags!=="string"||g.tags.length>500||(g.ip!==null&&(typeof g.ip!=="string"||g.ip.length>64))||metrics.some(k=>!nonnegative(g[k])))||new Set(inv.guests.map(g=>g.vmid)).size!==inv.guests.length)throw new Error("Ongeldige gastenlijst.");
 if(inv.nodes.some(n=>!n||!host(n.name)||typeof n.online!=="boolean"||[n.cpu,n.maxcpu,n.mem,n.maxmem].some(v=>!nonnegative(v)))||new Set(inv.nodes.map(n=>n.name)).size!==inv.nodes.length)throw new Error("Ongeldige nodelijst.");
 return {...inv,updatedAt:data.updatedAt,stale:data.stale};
}
export function enrichInventory(inventory:GuestInventory,monitor:unknown):GuestInventory {
 const nodes=(monitor as {nodes?:unknown}|null)?.nodes;
 if(!Array.isArray(nodes))return inventory;
 return {...inventory,guests:inventory.guests.map(guest=>{
  const node=nodes.find(n=>n&&n.name===guest.node&&!n.stale&&!n.error&&!n.loading);
  const row=Array.isArray(node?.guests)?node.guests.find((g:Guest)=>g.vmid===guest.vmid&&g.node===guest.node&&g.type===guest.type&&g.status===guest.status):null;
  if(!row)return guest;
  // Monitor counters are optional enrichment. Identity, status, allocation and IP stay canonical.
  const update:Partial<Guest>={};
  for(const key of ["diskread","diskwrite","netin","netout","updates"] as const){const value=row[key];if(typeof value==="number"&&Number.isFinite(value)&&value>=0&&value<=Number.MAX_SAFE_INTEGER)update[key]=value;}
  return {...guest,...update};
 })};
}
export function guestSelection(data:GuestInventory,node="cluster",status="all",query="") {
 const guests=data.guests.filter(g=>node==="cluster"||g.node===node);
 const nodes=data.nodes.filter(n=>node==="cluster"||n.name===node);
 const counts={all:guests.length,running:guests.filter(g=>g.status==="running").length,stopped:guests.filter(g=>g.status==="stopped").length};
 const words=query.trim().toLowerCase().split(/\s+/).filter(Boolean);
 const rows=guests.filter(g=>(status==="all"||g.status===status)&&words.every(w=>`${g.name} ${g.vmid} ${g.node} ${g.ip??""} ${g.tags}`.toLowerCase().includes(w)));
 return {guests,nodes,rows,counts};
}
export function guestTotals(guests:Guest[],nodes:GuestNode[]) {
 const sum=(values:(number|null)[])=>values.length&&values.every(v=>v!==null)?values.reduce<number>((a,v)=>a+(v??0),0):null;
 const cpuTotal=sum(nodes.map(n=>n.maxcpu)),memoryTotal=sum(nodes.map(n=>n.maxmem)),memoryUsed=sum(nodes.map(n=>n.mem));
 const cpuUsed=sum(nodes.map(n=>n.cpu!==null&&n.maxcpu!==null?n.cpu*n.maxcpu:null));
 return {cpuTotal,cpuPercent:cpuTotal&&cpuUsed!==null?cpuUsed/cpuTotal*100:null,memoryTotal,memoryUsed,memoryPercent:memoryTotal&&memoryUsed!==null?memoryUsed/memoryTotal*100:null,
  configured:guests.length?sum(guests.map(g=>g.maxcpu)):0,inUse:guests.filter(g=>g.status==="running").reduce((n,g)=>n+(g.maxcpu??0),0),allocatedMemory:guests.length?sum(guests.map(g=>g.maxmem)):0,
  diskUsed:guests.length?sum(guests.map(g=>g.disk)):0,diskTotal:guests.length?sum(guests.map(g=>g.maxdisk)):0};
}
export const guestPercent=(used:number|null,total:number|null)=>used!==null&&total!==null&&total>0?used/total*100:null;
export const guestGB=(n:number|null,digits=1)=>n===null?"—":(n/1024**3).toFixed(digits);
export function guestBytes(n:number|null){if(n===null)return "—";if(!n)return "0 B";const index=Math.max(0,Math.min(4,Math.floor(Math.log(n)/Math.log(1024))));return `${(n/1024**index).toFixed(index?1:0)} ${["B","KB","MB","GB","TB"][index]}`;}
export function guestUptime(n:number|null){if(n===null)return "—";return `${Math.floor(n/86400)}d ${Math.floor(n/3600)%24}h ${Math.floor(n/60)%60}m`;}
