/** Adapted from MacRimi/ProxMenux network-metrics.tsx and network-card.tsx,
 * GPL-3.0, d4e98d16b11733e518b0162db1b528b2ecd4cc53. Overview, dual traffic
 * headline, status chips and physical interface card structure retained.
 * Scoped CSS replaces Tailwind; safe cluster projection replaces direct API calls.
 */
import {Card,GuestIcon,Pair} from "./guest-cards";
import {guestBytes} from "../../lib/proxmox-guests";
import {latencySummary,networkSpeed,networkTotals,type NetworkInterface,type NetworkNode} from "../../lib/proxmox-network";
const count=(value:number|null)=>value===null?"—":value.toLocaleString("nl-NL");
const rate=(value:number|null)=>value===null?"—":`${guestBytes(value)}/s`;
const kinds={physical:"Physical",bridge:"Bridge",bond:"Bond",virtual:"VM / LXC"};
const colors={physical:"pm-blue",bridge:"pm-green",bond:"pm-purple",virtual:"pm-cyan"};
export function NetworkOverview({rows,nodes,incomplete=false}:{rows:NetworkInterface[];nodes:NetworkNode[];incomplete?:boolean}) {
 const t=networkTotals(rows),latency=latencySummary(nodes),total=(t.received??0)+(t.sent??0),down=total?100*(t.received??0)/total:50;
 const healthy=!incomplete&&t.errors===0&&t.drops===0;
 return <div className="pm-overview">
  <Card title="Network Traffic" icon="network"><div className="pm-net-traffic"><div><small>↓ Received</small><strong className="pm-green-text">{guestBytes(t.received)}</strong></div><div><small>↑ Sent</small><strong className="pm-blue-text">{guestBytes(t.sent)}</strong></div></div><div className="pm-net-strip"><i style={{width:`${down}%`,background:"#22c55e"}}/><i style={{flex:1,background:"#3b82f6"}}/></div><p className="pm-muted">Fysieke poorten · sinds tellerstart</p><div className="pm-summary-metrics"><Pair label="↓ Received now">{rate(t.rx)}</Pair><Pair label="↑ Sent now">{rate(t.tx)}</Pair></div></Card>
  <Card title="Active Interfaces" icon="network"><div className="pm-headline"><b>{t.physical.active+t.bridge.active}</b></div><div className="pm-pills"><span className="pm-badge pm-blue">Physical: {t.physical.active}/{t.physical.total}</span><span className="pm-badge pm-green">Bridges: {t.bridge.active}/{t.bridge.total}</span></div><p className="pm-muted">{t.physical.total+t.bridge.total} fysieke poorten en bridges</p><div className="pm-pills"><span className="pm-badge pm-purple">Bonds: {t.bond.active}/{t.bond.total}</span><span className="pm-badge pm-cyan">VM / LXC: {t.virtual.active}/{t.virtual.total}</span></div></Card>
  <Card title="Network Status" icon="network"><div className="pm-net-status"><strong>{count(t.errors)} <small>errors</small></strong><span className={`pm-badge ${healthy?"pm-green":t.errors!==null&&t.errors>0?"pm-red":""}`}>{incomplete?"Onvolledig":healthy?"✓ no errors / drops":t.errors===null||t.drops===null?"Unknown":"Controleer tellers"}</span></div><div className="pm-summary-metrics"><Pair label="Dropped packets">{count(t.drops)}</Pair><Pair label="Nodes">{nodes.length}</Pair><Pair label="DNS">{[...new Set(nodes.flatMap(n=>n.dns??[]))].join(", ")||"—"}</Pair><Pair label="Domain">{[...new Set(nodes.map(n=>n.domain).filter(Boolean))].join(", ")||"—"}</Pair></div></Card>
  <Card title="Gateway Latency" icon="network"><div className="pm-net-status"><strong>{latency.current??"—"} <small>ms</small></strong><span className="pm-badge">{incomplete||!latency.complete?"Onvolledig":"Hoogste nodewaarde"}</span></div><div className="pm-net-latencies">{nodes.map(n=><div key={n.name}><span className="pm-muted">{n.name}</span><strong>{n.latency?.current??"—"} ms</strong><LatencySparkline node={n}/></div>)}</div><p className="pm-muted">Gateway per node · afgelopen uur</p></Card>
 </div>;
}
export function LatencySparkline({node}:{node:NetworkNode}) {
 const history=node.latency?.history??[];
 if(history.length<2)return <span className="pm-muted">—</span>;
 const max=Math.max(...history.map(p=>p.value),1),minTime=history[0].time,span=history[history.length-1].time-minTime;
 if(span<=0)return <span className="pm-muted">—</span>;
 const points=history.map(p=>`${(p.time-minTime)/span*180},${36-p.value/max*32}`).join(" ");
 return <svg viewBox="0 0 180 40" className="pm-net-spark" role="img" aria-label={`Gateway latency ${node.name}: ${node.latency?.current??"onbekend"} ms`}><polyline points={points} fill="none" stroke="#3b82f6" strokeWidth="2"/></svg>;
}
export function InterfaceCard({item:i}:{item:NetworkInterface}) {
 const errors=i.errors_in===null||i.errors_out===null?null:i.errors_in+i.errors_out,drops=i.drops_in===null||i.drops_out===null?null:i.drops_in+i.drops_out;
 return <article className="pm-net-interface" aria-label={`${i.node} ${i.name}`}><header><div><GuestIcon kind="network"/><strong>{i.name}</strong><span className={`pm-badge ${colors[i.kind]}`}>{kinds[i.kind]}</span></div><span className={`pm-badge ${i.status==="up"?"pm-green":i.status==="down"?"pm-red":""}`}>{i.status.toUpperCase()}</span></header><div className="pm-net-sub"><span>{networkSpeed(i.speed)}{i.max_speed&&i.max_speed!==i.speed?` · max ${networkSpeed(i.max_speed)}`:""}</span><span>{i.duplex??"—"} duplex</span></div><div className="pm-net-stats"><Pair label="Node">{i.node}</Pair><Pair label="IP">{i.addresses.join(", ")||"—"}</Pair><Pair label="MTU">{i.mtu??"—"}</Pair>{i.used_by_bridges.length>0&&<Pair label="Bridges">{i.used_by_bridges.map(b=>`→ ${b}`).join(", ")}</Pair>}{i.bond_mode&&<Pair label="Bond mode">{i.bond_mode}</Pair>}{i.bond_active_slave&&<Pair label="Active slave">{i.bond_active_slave}</Pair>}{i.bond_slaves.length>0&&<Pair label="Slaves">{i.bond_slaves.join(", ")}</Pair>}{i.bridge_owner&&<Pair label="Master">{i.bridge_owner}</Pair>}{i.vm_name&&<Pair label={i.vm_type?.toUpperCase()??"Guest"}>{i.vm_name} · {i.vmid??"—"}</Pair>}<Pair label="↓ Received"><span className="pm-green-text">{rate(i.rx_Bps)}</span></Pair><Pair label="↑ Sent"><span className="pm-blue-text">{rate(i.tx_Bps)}</span></Pair><Pair label="↓ Total received">{guestBytes(i.bytes_recv)}</Pair><Pair label="↑ Total sent">{guestBytes(i.bytes_sent)}</Pair><Pair label="Errors">{count(errors)}</Pair><Pair label="Drops">{count(drops)}</Pair></div><footer>MAC {i.mac??"—"}</footer></article>;
}
export function NetworkInterfaces({rows,kind}:{rows:NetworkInterface[];kind:NetworkInterface["kind"]}) {
 const items=rows.filter(i=>i.kind===kind);
 if(!items.length)return null;
 return <section className="pm-card"><header className="pm-list-head"><h3><GuestIcon kind="network"/>{kind==="physical"?"Physical Interfaces":kind==="bridge"?"Network Bridges":kind==="bond"?"Network Bonds":"VM & LXC Interfaces"}</h3><span className="pm-badge">{items.length}</span></header><div className="pm-net-grid">{items.map(i=><InterfaceCard key={`${i.node}:${i.name}`} item={i}/>)}</div></section>;
}
export function NetworkTopology({nodes}:{nodes:NetworkNode[]}) {
 return <section className="pm-card"><header className="pm-list-head"><h3><GuestIcon kind="network"/>Network Flow</h3></header><div className="pm-list-content">{nodes.map(n=>{const rows=n.interfaces??[];return <div key={n.name} className="pm-net-topology"><strong>{n.name}</strong>{!rows.length?<span className="pm-muted">Geen topologie beschikbaar</span>:<div>{rows.filter(i=>i.kind==="physical").map(i=>{const bond=i.bond_master||(rows.find(r=>r.name===i.bridge_owner)?.kind==="bond"?i.bridge_owner:null);const bridges=i.used_by_bridges.length?i.used_by_bridges:i.bridge_owner&&!bond?[i.bridge_owner]:[];return <div className="pm-net-flow" key={i.name}><span className={`pm-badge ${i.status==="up"?"pm-green":""}`}>{i.name}</span>{bond&&<><span aria-hidden="true">→</span><span>{bond}</span></>}{bridges.length>0&&<><span aria-hidden="true">→</span><span className="pm-blue-text">{bridges.join(" / ")}</span></>}{!bond&&!bridges.length&&<span className="pm-muted">Geen master</span>}</div>;})}</div>}</div>;})}</div></section>;
}
