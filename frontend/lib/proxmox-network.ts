import type {GuestNode} from "./proxmox-guests";
export type NetworkInterface={bond_role?:"active"|"standby"|"member"|null;bond_link?:"up"|"down"|null;vm_status?:"running"|"stopped"|"paused"|null;node:string;name:string;kind:"physical"|"bond"|"bridge"|"virtual";status:"up"|"down"|"unknown";addresses:string[];mac:string|null;duplex:string|null;bytes_recv:number|null;bytes_sent:number|null;packets_recv:number|null;packets_sent:number|null;errors_in:number|null;errors_out:number|null;drops_in:number|null;drops_out:number|null;rx_Bps:number|null;tx_Bps:number|null;speed:number|null;max_speed:number|null;mtu:number|null;used_by_bridges:string[];bond_slaves:string[];bridge_members:string[];bridge_owner:string|null;bond_master:string|null;bond_active_slave:string|null;bridge_physical_interface:string|null;bond_mode:string|null;vmid:number|null;vm_name:string|null;vm_type:string|null};
export type NetworkNode={name:string;loading?:boolean;stale?:boolean;error?:string;partial?:string[];updatedAt?:number;networkAvailable?:boolean;hostname?:string|null;domain?:string|null;dns?:string[];interfaces?:NetworkInterface[];latency?:{current:number|null;avg:number|null;max:number|null;min:number|null;history:{time:number;value:number}[]}};
export type NetworkInventory={nodes:GuestNode[];updatedAt:number;stale:boolean};
const host=(s:unknown)=>typeof s==="string"&&/^[A-Za-z0-9][A-Za-z0-9.-]{0,62}$/.test(s);
const name=(s:unknown)=>typeof s==="string"&&/^[A-Za-z0-9_.:@-]{1,64}$/.test(s);
const bounded=(s:unknown,max=128)=>typeof s==="string"&&s.length<=max&&!/[\x00-\x1f]/.test(s);
const amount=(v:unknown)=>v===null||typeof v==="number"&&Number.isFinite(v)&&v>=0&&v<=Number.MAX_SAFE_INTEGER;
export function validateNetworkInventory(value:unknown):NetworkInventory {
 const data=value as {network?:NetworkInventory;updatedAt?:number;stale?:boolean}|null,body=data?.network;
 if(!body||!Array.isArray(body.nodes)||body.nodes.length>64||body.nodes.some(n=>!n||!host(n.name)||typeof n.online!=="boolean")||new Set(body.nodes.map(n=>n.name)).size!==body.nodes.length||typeof data.updatedAt!=="number"||!amount(data.updatedAt)||typeof data.stale!=="boolean")throw new Error("Ongeldige netwerk-node-inventaris.");
 return {...body,updatedAt:data.updatedAt,stale:data.stale};
}
export function validateNetworkMonitor(value:unknown):NetworkNode[] {
 const rows=(value as {nodes?:NetworkNode[]}|null)?.nodes;
 if(!Array.isArray(rows)||rows.length>64)throw new Error("Ongeldige netwerkmonitor.");
 for(const n of rows){
  if(!n||!host(n.name)||["loading","stale","networkAvailable"].some(k=>n[k as keyof NetworkNode]!==undefined&&typeof n[k as keyof NetworkNode]!=="boolean")||n.updatedAt!==undefined&&!amount(n.updatedAt)||n.error!==undefined&&!bounded(n.error,512)||n.partial!==undefined&&(!Array.isArray(n.partial)||n.partial.length>8||n.partial.some(v=>!bounded(v)))||n.dns!==undefined&&(!Array.isArray(n.dns)||n.dns.length>16||n.dns.some(v=>!bounded(v,64)))||[n.hostname,n.domain].some(v=>v!==undefined&&v!==null&&!bounded(v)))throw new Error("Ongeldige netwerkmonitor.");
  if(n.interfaces!==undefined){
   if(!Array.isArray(n.interfaces)||n.interfaces.length>8192)throw new Error("Ongeldige netwerklijst.");
   for(const i of n.interfaces){
    if(!i||i.bond_role!=null&&!["active","standby","member"].includes(i.bond_role)||i.bond_link!=null&&!["up","down"].includes(i.bond_link)||i.vm_status!=null&&!["running","stopped","paused"].includes(i.vm_status)||i.node!==n.name||!name(i.name)||!["physical","bridge","bond","virtual"].includes(i.kind)||!["up","down","unknown"].includes(i.status)||!Array.isArray(i.addresses)||i.addresses.length>32||i.addresses.some(v=>!bounded(v,64))||[i.bytes_recv,i.bytes_sent,i.packets_recv,i.packets_sent,i.errors_in,i.errors_out,i.drops_in,i.drops_out,i.rx_Bps,i.tx_Bps,i.speed,i.max_speed,i.mtu,i.vmid].some(v=>!amount(v))||[i.mac,i.duplex,i.bond_mode,i.vm_name,i.vm_type].some(v=>v!==null&&!bounded(v))||[i.bridge_owner,i.bond_master,i.bond_active_slave,i.bridge_physical_interface].some(v=>v!==null&&!name(v))||[i.used_by_bridges,i.bond_slaves,i.bridge_members].some(v=>!Array.isArray(v)||v.length>128||v.some(s=>!name(s))))throw new Error("Ongeldige interfacegegevens.");
   }
   if(new Set(n.interfaces.map(i=>i.name)).size!==n.interfaces.length)throw new Error("Dubbele netwerkinterface.");
  }
  if(n.latency&&([n.latency.current,n.latency.avg,n.latency.max,n.latency.min].some(v=>!amount(v))||!Array.isArray(n.latency.history)||n.latency.history.length>240||n.latency.history.some(p=>!p||typeof p.time!=="number"||!amount(p.time)||typeof p.value!=="number"||!amount(p.value))))throw new Error("Ongeldige latencygegevens.");
 }
 if(new Set(rows.map(n=>n.name)).size!==rows.length)throw new Error("Dubbele netwerkmonitor.");
 return rows;
}
export function networkSelection(data:NetworkInventory,monitor:NetworkNode[],scope="cluster") {
 const nodes=data.nodes.filter(n=>scope==="cluster"||n.name===scope);
 const relevant=monitor.filter(n=>nodes.some(host=>host.name===n.name)).sort((a,b)=>a.name.localeCompare(b.name));
 const incomplete=data.stale||nodes.some(n=>!n.online||!relevant.some(m=>m.name===n.name&&m.networkAvailable&&!m.loading&&!m.stale&&!m.error));
 return {nodes,monitor:relevant,interfaces:relevant.flatMap(n=>n.interfaces??[]),incomplete};
}
export function networkTotals(rows:NetworkInterface[]) {
 const physical=rows.filter(i=>i.kind==="physical");
 const sum=(key:"bytes_recv"|"bytes_sent"|"errors_in"|"errors_out"|"drops_in"|"drops_out"|"rx_Bps"|"tx_Bps")=>!physical.length||physical.some(i=>i[key]===null)?null:physical.reduce((n,i)=>n+(i[key]??0),0);
 const errorsIn=sum("errors_in"),errorsOut=sum("errors_out"),dropsIn=sum("drops_in"),dropsOut=sum("drops_out");
 const count=(kind:string)=>({total:rows.filter(i=>i.kind===kind).length,active:rows.filter(i=>i.kind===kind&&i.status==="up").length});
 return {received:sum("bytes_recv"),sent:sum("bytes_sent"),rx:sum("rx_Bps"),tx:sum("tx_Bps"),errors:errorsIn===null||errorsOut===null?null:errorsIn+errorsOut,drops:dropsIn===null||dropsOut===null?null:dropsIn+dropsOut,physical:count("physical"),bridge:count("bridge"),bond:count("bond"),virtual:count("virtual")};
}
export function networkSpeed(value:number|null) {return value===null||value===0?"—":value>=1000?`${+(value/1000).toFixed(2)} Gbps`:`${value} Mbps`;}
export function latencySummary(nodes:NetworkNode[]) {
 const known=nodes.filter(n=>!n.loading&&!n.error&&!n.stale&&n.latency?.current!==null&&n.latency?.current!==undefined);
 return {current:known.length?Math.max(...known.map(n=>n.latency!.current!)):null,complete:known.length===nodes.length&&nodes.length>0};
}
