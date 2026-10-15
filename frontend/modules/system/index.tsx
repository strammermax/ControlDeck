"use client";
import {useEffect,useState} from "react";
import type {ModuleViewProps,ModuleSettingsProps} from "../contracts";
import {loadMetric,MetricSourceError,metricLabels,metricSetting,type MetricRow} from "./metrics";
import {SystemCards} from "./cards";

export function View({settings}:ModuleViewProps) {
  const metric=metricSetting(settings.metric),node=settings.node??"";
  const [rows,setRows]=useState<MetricRow[]|null>(null),[error,setError]=useState(""),[updated,setUpdated]=useState("");
  useEffect(()=>{
    let active=true,busy=false;const controller=new AbortController();
    setRows(null);setError("");setUpdated("");
    const load=async()=>{
      if(busy)return;busy=true;
      try {
        const result=await loadMetric(metric,node,AbortSignal.any([controller.signal,AbortSignal.timeout(15000)]));
        if(active){setRows(result);setError("");setUpdated(new Date().toLocaleTimeString("nl-NL"));}
      }catch(failure){if(active){setError(failure instanceof MetricSourceError?failure.message:"Systeemgegevens kunnen niet worden vernieuwd.");setRows(current=>failure instanceof MetricSourceError&&failure.denied?null:current?.map(row=>({...row,stale:true}))??null);}}
      finally{busy=false;}
    };
    void load();const timer=setInterval(()=>void load(),60000);
    return()=>{active=false;controller.abort();clearInterval(timer);};
  },[metric,node]);
  return <section className="cd-system-widget" aria-label={metricLabels[metric]}>
    <div className="cd-system-toolbar"><span>{metricLabels[metric]}</span><a href="#proxmox">Proxmox ↗</a></div>
    {error&&<p role="alert">{error}</p>}
    {rows===null&&!error&&<p role="status">Systeemgegevens laden…</p>}
    {rows?.length===0&&<p role="status">{node?"Deze node is niet beschikbaar in de huidige bron.":"Geen nodes beschikbaar."}</p>}
    {rows&&<SystemCards metric={metric} rows={rows}/>}
    {updated&&<p className="cd-system-updated">Opgehaald om {updated} · vernieuwt iedere minuut</p>}
  </section>;
}
export function Settings({settings,onChange}:ModuleSettingsProps) {
  const metric=metricSetting(settings.metric);
  const [nodes,setNodes]=useState<string[]>([]),[error,setError]=useState("");
  useEffect(()=>{
    let active=true;const controller=new AbortController();
    loadMetric("cpu","",AbortSignal.any([controller.signal,AbortSignal.timeout(15000)]))
      .then(rows=>{if(active)setNodes(rows.map(row=>row.name));})
      .catch(()=>{if(active)setError("Nodelijst niet beschikbaar. Controleer de koppeling bij Proxmox.");});
    return()=>{active=false;controller.abort();};
  },[]);
  return <div><label>Meting<select value={metric} onChange={event=>onChange({metric:metricSetting(event.target.value),node:settings.node??""})}>{Object.entries(metricLabels).map(([id,title])=><option key={id} value={id}>{title}</option>)}</select></label><label>Node<select value={settings.node??""} onChange={event=>onChange({metric,node:event.target.value})}><option value="">Alle nodes</option>{settings.node&&!nodes.includes(settings.node)&&<option value={settings.node}>{settings.node} (opgeslagen)</option>}{nodes.map(node=><option key={node} value={node}>{node}</option>)}</select><small>Kies één host of toon alle nodes samen.</small></label>{error&&<p role="status">{error}</p>}</div>;
}
