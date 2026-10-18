import type {GuestNode} from "./proxmox-guests";
export type HardwareInventory={nodes:GuestNode[];updatedAt:number;stale:boolean};
export type MemoryModule={node:string;id:string;slot:string|null;size:number|null;type:string|null;configured_speed:string|null;max_speed:string|null;manufacturer:string|null};
export type ThermalSensor={node:string;id:string;kind:"cpu"|"gpu"|"nvme"|"hdd"|"ssd"|"pci"|"other";name:string|null;adapter:string|null;current:number|null;high:number|null;critical:number|null};
export type HardwareDevice={node:string;[key:string]:string|null};
export type HardwareNode={name:string;loading?:boolean;error?:string;stale?:boolean;partial?:string[];updatedAt?:number;hardwareAvailable?:boolean;memoryAvailable?:boolean;sensorsAvailable?:boolean;cpu?:{model:string|null;l3_cache:string|null;virtualization:string|null;sockets:number|null;cores_per_socket:number|null;total_threads:number|null};motherboard?:{manufacturer:string|null;model:string|null;bios:{vendor:string|null;version:string|null;date:string|null}};memory?:MemoryModule[];sensors?:ThermalSensor[];gpus?:HardwareDevice[];pci?:HardwareDevice[];usb?:HardwareDevice[];fans?:{node:string;name:string|null;speed:number|null;unit:string|null}[];power?:{node:string;name:string|null;watts:number|null}[]};
const amount=(n:unknown)=>n===null||typeof n==="number"&&Number.isFinite(n)&&n>=0&&n<=Number.MAX_SAFE_INTEGER;
const text=(v:unknown)=>v===null||typeof v==="string"&&v.length<=200&&!/[\x00-\x1f]/.test(v);
const host=(v:unknown)=>typeof v==="string"&&/^[A-Za-z0-9][A-Za-z0-9.-]{0,62}$/.test(v);
const thermal=(v:unknown)=>v===null||typeof v==="number"&&Number.isFinite(v)&&v>=-100&&v<=300;
export function validateHardwareInventory(value:unknown):HardwareInventory {
 const v=value as {hardware?:HardwareInventory;updatedAt?:number;stale?:boolean}|null;
 if(!v?.hardware||!Array.isArray(v.hardware.nodes)||v.hardware.nodes.length>64||v.hardware.nodes.some(n=>!n||!host(n.name)||typeof n.online!=="boolean")||new Set(v.hardware.nodes.map(n=>n.name)).size!==v.hardware.nodes.length||typeof v.updatedAt!=="number"||!amount(v.updatedAt)||typeof v.stale!=="boolean")throw new Error("Ongeldige hardware-node-inventaris.");
 return {...v.hardware,updatedAt:v.updatedAt,stale:v.stale};
}
export function validateHardwareMonitor(value:unknown):HardwareNode[] {
 const rows=(value as {nodes?:HardwareNode[]}|null)?.nodes;
 if(!Array.isArray(rows)||rows.length>64)throw new Error("Ongeldige hardwaremonitor.");
 for(const n of rows){
  if(!n||!host(n.name)||[n.loading,n.stale,n.hardwareAvailable,n.memoryAvailable,n.sensorsAvailable].some(v=>v!==undefined&&typeof v!=="boolean")||n.error!==undefined&&!text(n.error)||n.updatedAt!==undefined&&!amount(n.updatedAt)||n.partial!==undefined&&(!Array.isArray(n.partial)||n.partial.length>8||n.partial.some(p=>!text(p))))throw new Error("Ongeldige hardwaremonitor.");
  if(n.cpu&&([n.cpu.model,n.cpu.l3_cache,n.cpu.virtualization].some(v=>!text(v))||[n.cpu.sockets,n.cpu.cores_per_socket,n.cpu.total_threads].some(v=>!amount(v))))throw new Error("Ongeldige CPU-gegevens.");
  if(n.motherboard&&(!n.motherboard.bios||[n.motherboard.manufacturer,n.motherboard.model,n.motherboard.bios.vendor,n.motherboard.bios.version,n.motherboard.bios.date].some(v=>!text(v))))throw new Error("Ongeldig moederbord.");
  for(const key of ["memory","sensors","gpus","pci","usb","fans","power"] as const){const items=n[key];if(items!==undefined&&(!Array.isArray(items)||items.length>512||items.some(i=>!i||i.node!==n.name)))throw new Error("Ongeldige hardwarelijst.");}
  if(n.memory?.some(m=>!text(m.id)||typeof m.id!=="string"||![m.slot,m.type,m.configured_speed,m.max_speed,m.manufacturer].every(text)||!amount(m.size))||new Set(n.memory?.map(m=>m.id)).size!==(n.memory?.length??0))throw new Error("Ongeldige geheugenmodule.");
  if(n.sensors?.some(s=>typeof s.id!=="string"||!text(s.id)||!["cpu","gpu","nvme","hdd","ssd","pci","other"].includes(s.kind)||!text(s.name)||!text(s.adapter)||[s.current,s.high,s.critical].some(v=>!thermal(v)))||new Set(n.sensors?.map(s=>s.id)).size!==(n.sensors?.length??0))throw new Error("Ongeldige temperatuursensor.");
  if([...(n.gpus??[]),...(n.pci??[]),...(n.usb??[])].some(d=>Object.values(d).some(v=>!text(v))))throw new Error("Ongeldig hardwareapparaat.");
  if(n.fans?.some(f=>!text(f.name)||!text(f.unit)||!amount(f.speed))||n.power?.some(p=>!text(p.name)||!amount(p.watts)))throw new Error("Ongeldige ventilator-/vermogensmeting.");
 }
 if(new Set(rows.map(n=>n.name)).size!==rows.length)throw new Error("Dubbele hardwaremonitor.");
 return rows;
}
export function hardwareSelection(data:HardwareInventory,monitor:HardwareNode[],scope="cluster") {
 const nodes=data.nodes.filter(n=>scope==="cluster"||n.name===scope),relevant=monitor.filter(n=>nodes.some(host=>host.name===n.name));
 const incomplete=data.stale||nodes.some(n=>!n.online||!relevant.some(m=>m.name===n.name&&m.hardwareAvailable&&!m.loading&&!m.error&&!m.stale));
 return {nodes,monitor:relevant,incomplete};
}
export function sensorState(sensor:ThermalSensor):"unknown"|"normal"|"warning"|"critical" {
 if(sensor.current===null)return "unknown";
 if(sensor.current>=(sensor.critical!==null&&sensor.critical>0?sensor.critical:90))return "critical";
 if(sensor.current>=(sensor.high!==null&&sensor.high>0?sensor.high:80))return "warning";
 return "normal";
}
export function hardwareTotals(nodes:HardwareNode[]) {
 const memory=nodes.flatMap(n=>n.memory??[]),sensors=nodes.flatMap(n=>n.sensors??[]).filter(s=>s.current!==null);
 const complete=nodes.length>0&&nodes.every(n=>n.memoryAvailable&&!n.stale&&!n.loading&&!n.error)&&memory.every(m=>m.size!==null);
 return {memory:complete?memory.reduce((sum,m)=>sum+(m.size??0),0):null,modules:memory.length,sensors:sensors.length,hottest:sensors.length?Math.max(...sensors.map(s=>s.current!)):null};
}
