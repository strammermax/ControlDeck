"use client";
import {useEffect,useState} from "react";
import {storageSelection,storageMonitorSelection,storageTotals,validateStorage,validateStorageMonitor,type StorageInventory,type StorageMonitorNode} from "../lib/proxmox-storage";
import {StorageOverview,StorageList,RemoteMounts,PhysicalDisks} from "../modules/proxmox/storage-cards";
import "./proxmox-guests.css";
import "./proxmox-storage.css";

export function ProxmoxStorage({refreshSeconds=60}:{refreshSeconds?:number}) {
 const [data,setData]=useState<StorageInventory|null>(null),[monitor,setMonitor]=useState<StorageMonitorNode[]>([]),[error,setError]=useState(""),[pending,setPending]=useState(false);
 useEffect(()=>{
  let active=true,busy=false;const controller=new AbortController();
  const load=async()=>{
   if(busy)return;busy=true;
   try{
    const signal=AbortSignal.any([controller.signal,AbortSignal.timeout(25000)]);
    const [response,mon]=await Promise.all([fetch("/api/proxmox/storage",{cache:"no-store",signal}),fetch("/api/proxmenux/storage",{cache:"no-store",signal}).then(async r=>r.ok?validateStorageMonitor(await r.json()):[]).catch(()=>[])]);
    if([401,403,409].includes(response.status)){if(active){setData(null);setMonitor([]);}throw new Error(response.status===409?"Koppel eerst Proxmox via Admin → Modules.":"Je hebt geen toegang tot dit opslagoverzicht.");}
    if(!response.ok)throw new Error("De opslaginventaris is niet beschikbaar.");
    const inventory=validateStorage(await response.json());
    if(active){setData(inventory);setMonitor(mon);setPending(mon.some(n=>n.loading));setError("");}
   }catch(failure){if(active){setError(failure instanceof Error?failure.message:"Opslaggegevens kunnen niet worden vernieuwd.");setData(old=>old?{...old,stale:true}:null);setMonitor([]);}}
   finally{busy=false;}
  };
  void load();const timer=setInterval(()=>void load(),pending?5000:Math.max(30,refreshSeconds)*1000);
  return()=>{active=false;controller.abort();clearInterval(timer);};
 },[refreshSeconds,pending]);
 return <section className="pm-vms pm-storage" aria-label="Proxmox opslag">{error&&<p role="alert" className="config-error">{error}</p>}{!data&&!error&&<p role="status">Clusteropslag laden…</p>}{data&&<StorageInventoryView data={data} monitor={monitor}/>}</section>;
}
export function StorageInventoryView({data,monitor}:{data:StorageInventory;monitor:StorageMonitorNode[]}) {
 const [scope,setScope]=useState("cluster");
 const names=[...new Set([...data.nodes.map(n=>n.name),...data.storage.map(s=>s.node)])].sort();
 const selected=names.includes(scope)?scope:"cluster",view=storageSelection(data,selected);
 const relevant=storageMonitorSelection(monitor,view.nodes);
 const disks=relevant.flatMap(n=>n.disks??[]),pools=relevant.flatMap(n=>n.pools??[]),mounts=relevant.flatMap(n=>n.mounts??[]);
 const incomplete=view.nodes.some(node=>!node.online||!relevant.some(n=>n.name===node.name&&n.disksAvailable&&n.mountsAvailable&&!n.loading&&!n.stale&&!n.error&&!n.partial?.length));
 const totals=storageTotals(view.storage),partial=data.stale||!data.identityComplete||incomplete||totals.local.incomplete||totals.remote.incomplete||view.storage.some(r=>r.status!=="active"||r.category==="unknown"||r.unavailableNodes.length>0);
 return <><div className="pm-scope" role="group" aria-label="Cluster of node">{["cluster",...names].map(name=><button key={name} type="button" aria-pressed={selected===name} onClick={()=>setScope(name)}>{name==="cluster"?"Cluster":name}</button>)}</div>
  {partial&&<p role="status" className="config-error">{data.stale?"De opslaginventaris is verouderd. ":""}Niet alle opslagmetingen zijn beschikbaar. Onbekende waarden blijven —; totalen beschrijven de bekende actieve opslag.</p>}
  <StorageOverview storage={view.storage} disks={disks} incomplete={incomplete}/><StorageList rows={view.storage}/><RemoteMounts rows={mounts.filter(m=>m.scope==="host")} title="Remote Mounts"/>{mounts.some(m=>m.scope==="container")&&<RemoteMounts rows={mounts.filter(m=>m.scope==="container")} title="LXC Remote Mounts"/>}<PhysicalDisks disks={disks} pools={pools}/>
  <p className="pm-footnote">Bijgewerkt: {new Date(data.updatedAt*1000).toLocaleTimeString("nl-NL")} · Gedeelde opslag telt clusterbreed één keer. Mounts, fysieke schijven en ZFS-pools worden niet nogmaals bij het opslagverbruik opgeteld.</p>
 </>;
}
