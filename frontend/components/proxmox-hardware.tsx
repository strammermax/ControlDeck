"use client";
import {useEffect,useState} from "react";
import {hardwareSelection,validateHardwareInventory,validateHardwareMonitor,type HardwareInventory,type HardwareNode} from "../lib/proxmox-hardware";
import {SystemInformation,MemoryModules,ThermalMonitoring,HardwareDevices,HardwarePower} from "../modules/proxmox/hardware-cards";
import "./proxmox-guests.css";
import "./proxmox-hardware.css";

export function ProxmoxHardware({refreshSeconds=60}:{refreshSeconds?:number}) {
 const [data,setData]=useState<HardwareInventory|null>(null),[monitor,setMonitor]=useState<HardwareNode[]>([]),[error,setError]=useState(""),[pending,setPending]=useState(false);
 useEffect(()=>{
  let active=true,busy=false;const controller=new AbortController();
  const load=async()=>{
   if(busy)return;busy=true;
   try{
    const signal=AbortSignal.any([controller.signal,AbortSignal.timeout(25000)]);
    const [response,mon]=await Promise.all([fetch("/api/proxmox/hardware",{cache:"no-store",signal}),fetch("/api/proxmenux/hardware",{cache:"no-store",signal}).then(async r=>r.ok?validateHardwareMonitor(await r.json()):[]).catch(()=>[])]);
    if([401,403,409].includes(response.status)){if(active){setData(null);setMonitor([]);}throw new Error(response.status===409?"Koppel eerst Proxmox en ProxMenux via Admin → Modules.":"Je hebt geen toegang tot dit hardwareoverzicht.");}
    if(!response.ok)throw new Error("De hardware-node-inventaris is niet beschikbaar.");
    const inventory=validateHardwareInventory(await response.json());
    if(active){setData(inventory);setMonitor(mon);setPending(mon.some(n=>n.loading));setError("");}
   }catch(failure){if(active){setError(failure instanceof Error?failure.message:"Hardwaregegevens kunnen niet worden vernieuwd.");setData(old=>old?{...old,stale:true}:null);setMonitor([]);}}
   finally{busy=false;}
  };
  void load();const timer=setInterval(()=>void load(),pending?5000:Math.max(30,refreshSeconds)*1000);
  return()=>{active=false;controller.abort();clearInterval(timer);};
 },[refreshSeconds,pending]);
 return <section className="pm-vms pm-hardware" aria-label="Proxmox hardware">{error&&<p role="alert" className="config-error">{error}</p>}{!data&&!error&&<p role="status">Clusterhardware laden…</p>}{data&&<HardwareInventoryView data={data} monitor={monitor}/>}</section>;
}
export function HardwareInventoryView({data,monitor}:{data:HardwareInventory;monitor:HardwareNode[]}) {
 const [scope,setScope]=useState("cluster");
 const names=data.nodes.map(n=>n.name).sort(),selected=names.includes(scope)?scope:"cluster",view=hardwareSelection(data,monitor,selected);
 const displayNodes=view.nodes.map(n=>view.monitor.find(m=>m.name===n.name)??{name:n.name});
 const gpus=view.monitor.flatMap(n=>n.gpus??[]),pci=view.monitor.flatMap(n=>n.pci??[]),usb=view.monitor.flatMap(n=>n.usb??[]);
 return <><div className="pm-scope" role="group" aria-label="Cluster of node">{["cluster",...names].map(name=><button key={name} type="button" aria-pressed={selected===name} onClick={()=>setScope(name)}>{name==="cluster"?"Cluster":name}</button>)}</div>
 {view.incomplete&&<p role="status" className="config-error">Niet alle hardwaremetingen zijn beschikbaar. Ontbrekende waarden blijven —; oudere gegevens zijn mogelijk verouderd.</p>}
 {displayNodes.map(n=><SystemInformation key={n.name} node={n}/>)}<MemoryModules nodes={displayNodes}/><ThermalMonitoring nodes={displayNodes}/><HardwarePower nodes={displayNodes}/><HardwareDevices title="Graphics Cards" rows={gpus} fields={[["vendor","Vendor"],["slot","PCI slot"],["driver","Driver"],["type","Type"]]}/><HardwareDevices title="PCI Devices" rows={pci} fields={[["vendor","Vendor"],["slot","PCI slot"],["class","Class"],["driver","Driver"],["kernel_module","Kernel module"]]}/><HardwareDevices title="USB Devices" rows={usb} fields={[["vendor","Vendor"],["bus_device","Bus / Device"],["class_label","Class"],["driver","Driver"],["speed_label","Speed"]]}/>
 <p className="pm-footnote">CPU, moederbord, geheugenbanken en sensoren blijven per node herkenbaar. Geheugen wordt in bytes opgeteld; temperaturen worden nooit opgeteld. Serialnummers en beheeracties worden niet getoond. Hardware wordt met de ingestelde verversperiode bijgewerkt.</p>
 </>;
}
