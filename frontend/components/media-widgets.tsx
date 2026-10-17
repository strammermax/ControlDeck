"use client";
import {useEffect,useState} from "react";
import {mediaFamilies,mediaSourceRows,widgetRequest,type MediaFamily,type WidgetSource} from "../lib/service-widgets";
import {serviceModule} from "../modules/service";
const views={downloads:serviceModule("downloads").View,"media-widget":serviceModule("media-widget").View,tdarr:serviceModule("tdarr").View};
const labels={downloads:"Downloads","media-widget":"Films en series",tdarr:"Tdarr"};
export function MediaWidgets({csrfToken}:{csrfToken:string}) {
 const [rows,setRows]=useState<(WidgetSource&{family:MediaFamily})[]>([]),[error,setError]=useState(""),[loading,setLoading]=useState(true);
 useEffect(()=>{
  let active=true;const controller=new AbortController();
  Promise.all(mediaFamilies.map(family=>widgetRequest<unknown>(`/api/widget-sources?family=${family}`,AbortSignal.any([controller.signal,AbortSignal.timeout(20000)]))))
   .then(values=>{const sources=mediaSourceRows(values);if(active)setRows(sources);})
   .catch(()=>{if(active)setError("Mediabronnen zijn niet beschikbaar. Controleer de koppelingen en je toegang.");})
   .finally(()=>{if(active)setLoading(false);});
  return()=>{active=false;controller.abort();};
 },[]);
 return <div className="cd-media-page"><p>Je downloaders, films, series en verwerking. Dezelfde modules kun je afzonderlijk aan je dashboard toevoegen.</p>{loading&&<p role="status">Mediabronnen laden…</p>}{error&&<p role="alert">{error}</p>}{!loading&&!error&&!rows.length&&<p>Er zijn nog geen mediabronnen voor jouw account ingesteld.</p>}<div className="cd-media-grid">{rows.map(source=>{const View=views[source.family];return <section key={`${source.family}:${source.id}`} className="cd-media-panel"><h3>{labels[source.family]}</h3><View settings={{sourceId:source.id}} csrfToken={csrfToken}/></section>;})}</div></div>;
}
