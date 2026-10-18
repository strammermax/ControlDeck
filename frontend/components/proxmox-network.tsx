"use client";
import {useEffect,useState} from "react";
import {networkSelection,validateNetworkInventory,validateNetworkMonitor,type NetworkInventory,type NetworkNode} from "../lib/proxmox-network";
import {NetworkOverview,NetworkInterfaces,NetworkTopology} from "../modules/proxmox/network-cards";
import "./proxmox-guests.css";
import "./proxmox-network.css";

export function ProxmoxNetwork({refreshSeconds=60}:{refreshSeconds?:number}) {
 const [data,setData]=useState<NetworkInventory|null>(null),[monitor,setMonitor]=useState<NetworkNode[]>([]),[error,setError]=useState(""),[pending,setPending]=useState(false);
 useEffect(()=>{
  let active=true,busy=false;const controller=new AbortController();
  const load=async()=>{
   if(busy)return;busy=true;
   try{
    const signal=AbortSignal.any([controller.signal,AbortSignal.timeout(25000)]);
    const [response,mon]=await Promise.all([fetch("/api/proxmox/network",{cache:"no-store",signal}),fetch("/api/proxmenux/network",{cache:"no-store",signal}).then(async r=>r.ok?validateNetworkMonitor(await r.json()):[]).catch(()=>[])]);
    if([401,403,409].includes(response.status)){if(active){setData(null);setMonitor([]);}throw new Error(response.status===409?"Koppel eerst Proxmox en ProxMenux via Admin → Modules.":"Je hebt geen toegang tot dit netwerkoverzicht.");}
    if(!response.ok)throw new Error("De netwerk-node-inventaris is niet beschikbaar.");
    const inventory=validateNetworkInventory(await response.json());
    if(active){setData(inventory);setMonitor(mon);setPending(mon.some(n=>n.loading));setError("");}
   }catch(failure){if(active){setError(failure instanceof Error?failure.message:"Netwerkgegevens kunnen niet worden vernieuwd.");setData(old=>old?{...old,stale:true}:null);setMonitor([]);}}
   finally{busy=false;}
  };
  void load();const timer=setInterval(()=>void load(),pending?5000:Math.max(30,refreshSeconds)*1000);
  return()=>{active=false;controller.abort();clearInterval(timer);};
 },[refreshSeconds,pending]);
 return <section className="pm-vms pm-network" aria-label="Proxmox netwerk">{error&&<p role="alert" className="config-error">{error}</p>}{!data&&!error&&<p role="status">Clusternetwerk laden…</p>}{data&&<NetworkInventoryView data={data} monitor={monitor}/>}</section>;
}
export function NetworkInventoryView({data,monitor}:{data:NetworkInventory;monitor:NetworkNode[]}) {
 const [scope,setScope]=useState("cluster"),[query,setQuery]=useState("");
 const names=data.nodes.map(n=>n.name).sort(),selected=names.includes(scope)?scope:"cluster",view=networkSelection(data,monitor,selected);
 const rows=view.interfaces.filter(i=>`${i.node} ${i.name} ${i.vm_name??""} ${i.vmid??""} ${i.addresses.join(" ")}`.toLowerCase().includes(query.toLowerCase()));
 return <><div className="pm-net-controls"><div className="pm-scope" role="group" aria-label="Cluster of node">{["cluster",...names].map(name=><button key={name} type="button" aria-pressed={selected===name} onClick={()=>setScope(name)}>{name==="cluster"?"Cluster":name}</button>)}</div><input aria-label="Zoek netwerkinterface" placeholder="Zoek interface, IP of VM…" value={query} onChange={event=>setQuery(event.target.value)}/></div>
 {view.incomplete&&<p role="status" className="config-error">Niet alle netwerkmetingen zijn beschikbaar. Totalen beschrijven de bekende fysieke poorten; ontbrekende waarden blijven —.</p>}
 <NetworkOverview rows={view.interfaces} nodes={view.monitor} incomplete={view.incomplete}/><NetworkTopology nodes={view.monitor}/>{view.interfaces.length===0&&<p className="pm-net-empty">Nog geen netwerkgegevens beschikbaar. Controleer de ProxMenux-koppeling via Admin → Modules.</p>}{query&&rows.length===0&&<p role="status">Geen interfaces gevonden voor deze zoekopdracht.</p>}{(["physical","bond","bridge","virtual"] as const).map(kind=><NetworkInterfaces key={kind} kind={kind} rows={rows}/>)}
 <p className="pm-footnote">Fysieke poorten tellen clusterbreed één keer per node. Intern clusterverkeer passeert meerdere hosts; dit is geen uniek internetverbruik. Bridges, bonds en VM/LXC-interfaces worden niet opnieuw opgeteld. RX/TX komt uit de monitor of twee opeenvolgende tellermetingen; bij ontbrekende metingen of een tellerreset blijft de snelheid —. Latency wordt per gateway getoond; de clusterkaart gebruikt de hoogste nodewaarde.</p>
 </>;
}
