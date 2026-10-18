"use client";
import {useEffect,useState} from "react";
import {enrichInventory,guestSelection,validateInventory,type GuestInventory} from "../lib/proxmox-guests";
import {GuestCard,GuestIcon,GuestOverview} from "../modules/proxmox/guest-cards";
import "./proxmox-guests.css";

export function ProxmoxGuests({refreshSeconds=60}:{refreshSeconds?:number}) {
 const [data,setData]=useState<GuestInventory|null>(null),[error,setError]=useState(""),[monitorWarning,setMonitorWarning]=useState(false);
 useEffect(()=>{
  let active=true,busy=false;const controller=new AbortController();
  const load=async()=>{
   if(busy)return;busy=true;
   try{
    const signal=AbortSignal.any([controller.signal,AbortSignal.timeout(30000)]);
    const [response,monitor]=await Promise.all([fetch("/api/proxmox/guests",{cache:"no-store",signal}),fetch("/api/proxmenux/summary",{cache:"no-store",signal}).then(async r=>r.ok?await r.json():null).catch(()=>null)]);
    if([401,403].includes(response.status)){if(active)setData(null);throw new Error("Je hebt geen toegang tot dit Proxmox-overzicht.");}
    if(!response.ok){if(active)setData(null);throw new Error(response.status===409?"Koppel eerst Proxmox via Admin → Modules.":"Het clusteroverzicht is niet beschikbaar.");}
    const inventory=validateInventory(await response.json());
    if(active){setData(enrichInventory(inventory,monitor));setError("");setMonitorWarning(!Array.isArray(monitor?.nodes)||inventory.nodes.some(node=>!monitor.nodes.some((n:{name:string})=>n.name===node.name))||monitor.nodes.some((n:{stale?:boolean;error?:string;loading?:boolean})=>n.stale||n.error||n.loading));}
   }catch(failure){if(active){setError(failure instanceof Error?failure.message:"Het clusteroverzicht is niet bereikbaar.");setData(previous=>previous?{...previous,stale:true}:null);}}
   finally{busy=false;}
  };
  void load();const timer=setInterval(()=>void load(),Math.max(30,refreshSeconds)*1000);
  return()=>{active=false;controller.abort();clearInterval(timer);};
 },[refreshSeconds]);
 return <section className="pm-vms" aria-label="Proxmox VM's en containers">{error&&<p role="alert" className="config-error">{error}</p>}{!data&&!error&&<p role="status">VM's en containers clusterbreed laden…</p>}{data&&<GuestInventoryView data={data} monitorWarning={monitorWarning}/>}</section>;
}
export function GuestInventoryView({data,monitorWarning=false}:{data:GuestInventory;monitorWarning?:boolean}) {
 const [node,setNode]=useState("cluster"),[status,setStatus]=useState("all"),[query,setQuery]=useState("");
 const names=[...new Set([...data.nodes.map(n=>n.name),...data.guests.map(g=>g.node)])].sort();
 const selected=names.includes(node)?node:"cluster";
 const view=guestSelection(data,selected,status,query);
 const offline=view.nodes.filter(n=>!n.online).map(n=>n.name);
 return <>
  <div className="pm-scope" role="group" aria-label="Cluster of node">{["cluster",...names].map(name=><button type="button" key={name} aria-pressed={selected===name} onClick={()=>setNode(name)}>{name==="cluster"?"Cluster":name}</button>)}</div>
  {(data.stale||offline.length>0)&&<p role="status" className="config-error">{data.stale?"De gegevens zijn verouderd. ":""}{offline.length?`Niet bereikbare nodes: ${offline.join(", ")}. Het overzicht kan onvolledig zijn.`:"De laatst bekende gegevens worden getoond."}</p>}
  {monitorWarning&&<p className="pm-source-warning" role="status">ProxMenux-gegevens zijn nog niet volledig beschikbaar. De Proxmox-inventaris blijft zichtbaar; ontbrekende metingen worden als — getoond.</p>}
  <GuestOverview guests={view.guests} nodes={view.nodes}/>
  <section className="pm-card pm-list"><header className="pm-list-head"><h3><GuestIcon/>Virtual Machines &amp; Containers</h3><div className="pm-scope pm-status-filter" role="group" aria-label="Filter op status">{(["all","running","stopped"] as const).map(key=><button key={key} type="button" aria-pressed={status===key} onClick={()=>setStatus(key)}>{key!=="all"&&<GuestIcon kind={key}/>}<span>{key==="all"?"All":key==="running"?"Running":"Stopped"}</span><small>{view.counts[key]}</small></button>)}</div></header>
   <div className="pm-list-content"><label className="pm-search"><span className="sr-only">Zoek VM of container</span><input type="search" value={query} maxLength={200} placeholder="Zoek op naam, ID, node, IP of tag…" onChange={e=>setQuery(e.target.value)}/></label>{view.rows.length?view.rows.map(guest=><GuestCard key={guest.vmid} guest={guest}/>):<p role="status">Geen VM's of containers gevonden voor deze selectie.</p>}</div>
  </section><p className="pm-footnote">Bijgewerkt: {new Date(data.updatedAt*1000).toLocaleTimeString("nl-NL")} · ProxMenux-weergave · I/O toont tellers sinds de start, geen snelheden.</p>
 </>;
}
