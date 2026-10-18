/** Adapted from MacRimi/ProxMenux AppImage/components/hardware.tsx,
 * GPL-3.0, d4e98d16b11733e518b0162db1b528b2ecd4cc53 (system, DIMM and
 * thermal layout from line 650). Scoped CSS/shared primitives replace Tailwind.
 * No driver installers, passthrough changes or privileged actions imported.
 */
import type {ReactNode} from "react";
import {Bar,GuestIcon,Pair} from "./guest-cards";
import {guestBytes} from "../../lib/proxmox-guests";
import {hardwareTotals,sensorState,type HardwareNode,type ThermalSensor,type HardwareDevice} from "../../lib/proxmox-hardware";
function Section({title,icon="cpu",badge,children}:{title:string;icon?:string;badge?:ReactNode;children:ReactNode}) {return <section className="pm-card pm-hw-section"><header className="pm-list-head"><h3><GuestIcon kind={icon}/>{title}</h3>{badge&&<span className="pm-badge">{badge}</span>}</header><div className="pm-hw-content">{children}</div></section>;}
export function SystemInformation({node}:{node:HardwareNode}) {
 const cpu=node.cpu,board=node.motherboard;
 const cores=cpu?.sockets!==null&&cpu?.sockets!==undefined&&cpu?.cores_per_socket!==null&&cpu?.cores_per_socket!==undefined?`${cpu.sockets} × ${cpu.cores_per_socket} = ${cpu.sockets*cpu.cores_per_socket} cores`:"—";
 return <Section title="System Information" badge={node.name}><div className="pm-hw-two"><div><h4><GuestIcon kind="cpu"/>CPU</h4><Pair label="Model">{cpu?.model??"—"}</Pair><Pair label="Cores">{cores}</Pair><Pair label="Threads">{cpu?.total_threads??"—"}</Pair><Pair label="L3 Cache">{cpu?.l3_cache??"—"}</Pair><Pair label="Virtualization">{cpu?.virtualization??"—"}</Pair></div><div><h4><GuestIcon kind="cpu"/>Motherboard</h4><Pair label="Manufacturer">{board?.manufacturer??"—"}</Pair><Pair label="Model">{board?.model??"—"}</Pair><Pair label="BIOS">{board?.bios.vendor??"—"}</Pair><Pair label="Version">{board?.bios.version??"—"}</Pair><Pair label="Date">{board?.bios.date??"—"}</Pair></div></div></Section>;
}
export function MemoryModules({nodes}:{nodes:HardwareNode[]}) {
 const rows=nodes.flatMap(n=>n.memory??[]),totals=hardwareTotals(nodes);
 return <Section title="Memory Modules" icon="memory" badge={`${rows.length} installed · ${guestBytes(totals.memory)}`}><div className="pm-hw-grid">{rows.map(m=><article key={`${m.node}:${m.id}`} className="pm-hw-device"><header><strong>{m.slot??"Memory module"}</strong><span className="pm-muted">{m.node}</span></header><Pair label="Size"><span className="pm-green-text">{guestBytes(m.size)}</span></Pair><Pair label="Type">{m.type??"—"}</Pair><Pair label="Speed">{m.configured_speed??m.max_speed??"—"}{m.configured_speed&&m.max_speed&&m.configured_speed!==m.max_speed?` (max ${m.max_speed})`:""}</Pair><Pair label="Manufacturer">{m.manufacturer??"—"}</Pair></article>)}</div>{!rows.length&&<p className="pm-muted">Geen geheugenmodules gemeld.</p>}{nodes.some(n=>!n.memoryAvailable)&&<p role="status" className="pm-muted">Geheugeninventaris ontbreekt voor een of meer nodes.</p>}</Section>;
}
const sensorNames={cpu:"CPU",gpu:"GPU",nvme:"NVME",hdd:"HDD",ssd:"SSD",pci:"PCI",other:"Other"};
export function ThermalReading({sensor:s}:{sensor:ThermalSensor}) {
 const state=sensorState(s),limit=s.critical!==null&&s.critical>0?s.critical:100;
 const color=state==="critical"?"#ef4444":state==="warning"?"#f59e0b":state==="normal"?"#22c55e":"var(--muted)";
 return <article className="pm-hw-sensor"><div><strong>{s.name??"Sensor"}</strong><strong style={{color}}>{s.current===null?"—":`${s.current.toFixed(1)}°C`}</strong></div><Bar value={s.current===null?null:100*s.current/limit} color={state==="critical"?"#ef4444":state==="warning"?"#f59e0b":"#3b82f6"}/><div className="pm-muted"><span>{s.node} · {s.adapter??"Sensor"}</span><span>{state==="critical"?"Kritiek":state==="warning"?"Hoog":state==="unknown"?"Onbekend":""}</span></div></article>;
}
export function ThermalMonitoring({nodes}:{nodes:HardwareNode[]}) {
 const rows=nodes.flatMap(n=>n.sensors??[]);
 return <Section title="Thermal Monitoring" badge={`${rows.length} sensors`}>{(Object.keys(sensorNames) as ThermalSensor["kind"][]).map(kind=>{const items=rows.filter(s=>s.kind===kind);return items.length>0&&<div className="pm-hw-thermal-group" key={kind}><h4><GuestIcon kind={kind==="nvme"||kind==="hdd"||kind==="ssd"?"disk":"cpu"}/>{sensorNames[kind]} <span className="pm-badge">{items.length}</span></h4><div className="pm-hw-two">{items.map(s=><ThermalReading key={`${s.node}:${s.id}`} sensor={s}/>)}</div></div>;})}{!rows.length&&<p className="pm-muted">Geen temperatuursensoren gemeld.</p>}{nodes.some(n=>!n.sensorsAvailable)&&<p role="status" className="pm-muted">Temperatuurmetingen ontbreken voor een of meer nodes.</p>}</Section>;
}
export function HardwareDevices({title,rows,fields}:{title:string;rows:HardwareDevice[];fields:[string,string][]}) {
 if(!rows.length)return null;
 return <Section title={title} badge={rows.length}><div className="pm-hw-grid">{rows.map((d,index)=><article className="pm-hw-device" key={`${d.node}:${index}`}><header><strong>{d.name??d.device??d.slot??"Device"}</strong><span className="pm-muted">{d.node}</span></header>{fields.map(([key,label])=><Pair key={key} label={label}>{d[key]??"—"}</Pair>)}</article>)}</div></Section>;
}
export function HardwarePower({nodes}:{nodes:HardwareNode[]}) {
 const fans=nodes.flatMap(n=>n.fans??[]),power=nodes.flatMap(n=>n.power??[]);
 if(!fans.length&&!power.length)return null;
 return <Section title="Fans & Power"><div className="pm-hw-grid">{fans.map((f,i)=><article className="pm-hw-device" key={`fan:${f.node}:${i}`}><header><strong>{f.name??"Fan"}</strong><span className="pm-muted">{f.node}</span></header><Pair label="Speed">{f.speed===null?"—":`${f.speed} ${f.unit??"RPM"}`}</Pair></article>)}{power.map((p,i)=><article className="pm-hw-device" key={`power:${p.node}:${i}`}><header><strong>{p.name??"Power"}</strong><span className="pm-muted">{p.node}</span></header><Pair label="Power">{p.watts===null?"—":`${p.watts.toFixed(1)} W`}</Pair></article>)}</div></Section>;
}
