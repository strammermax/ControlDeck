"use client";
import {useEffect,useState} from "react";
import {WidgetError,validateWidgetData,validateWidgetSources,widgetPath,widgetRequest,type ServiceFamily,type WidgetSource,type WidgetData} from "../../lib/service-widgets";
import type {ModuleViewProps,ModuleSettingsProps} from "../contracts";
import {ServiceCards} from "./cards";

/** Family modules share lifecycle and presentation, not credentials or source permissions. */
export function serviceModule(family:ServiceFamily) {
  function View({settings}:ModuleViewProps) {
    const id=settings.sourceId??"";
    const [data,setData]=useState<WidgetData|null>(null),[error,setError]=useState("");
    useEffect(()=>{
      let active=true,busy=false;const controller=new AbortController();setData(null);setError("");
      if(!id)return()=>controller.abort();
      const load=async()=>{
        if(busy)return;busy=true;
        try{
          const value=validateWidgetData(await widgetRequest<unknown>(widgetPath(family,id),AbortSignal.any([controller.signal,AbortSignal.timeout(20000)])));
          if(active){setData(value);setError("");}
        }catch(failure){if(active){setError(failure instanceof WidgetError?failure.message:"Widgetgegevens zijn niet beschikbaar.");setData(current=>failure instanceof WidgetError&&failure.denied?null:current?{...current,stale:true}:null);}}
        finally{busy=false;}
      };
      void load();const timer=setInterval(()=>void load(),60000);
      return()=>{active=false;controller.abort();clearInterval(timer);};
    },[id]);
    return <section className="cd-service-widget">{!id?<p>Kies een bron via Aanpassen. Verbindingen worden centraal in Infisical ingericht.</p>:<>{data?.sourceTitle&&<p className="cd-widget-source">{data.sourceTitle}</p>}{error&&<p role="alert">{error}</p>}{!data&&!error&&<p role="status">Widget laden…</p>}{data&&<ServiceCards data={data}/>}</>}</section>;
  }
  function Settings({settings,onChange}:ModuleSettingsProps) {
    const [sources,setSources]=useState<WidgetSource[]>([]),[error,setError]=useState(""),[loading,setLoading]=useState(true);
    useEffect(()=>{
      let active=true;const controller=new AbortController();
      widgetRequest<{sources:WidgetSource[]}>(`/api/widget-sources?family=${family}`,AbortSignal.any([controller.signal,AbortSignal.timeout(20000)]))
        .then(value=>{const rows=validateWidgetSources(value);if(active)setSources(rows);}).catch(()=>{if(active)setError("Bronnen niet beschikbaar. Controleer Infisical en je toegangsrechten.");}).finally(()=>{if(active)setLoading(false);});
      return()=>{active=false;controller.abort();};
    },[]);
    return <label>Bron<select value={settings.sourceId??""} onChange={event=>onChange({sourceId:event.target.value})}><option value="">Kies een bron</option>{settings.sourceId&&!sources.some(s=>s.id===settings.sourceId)&&<option value={settings.sourceId}>Opgeslagen bron (niet beschikbaar)</option>}{sources.map(source=><option key={source.id} value={source.id}>{source.title}</option>)}</select>{loading&&<span role="status">Bronnen laden…</span>}{error&&<span role="status">{error}</span>}{!loading&&!error&&!sources.length&&<span>Er zijn nog geen bronnen voor jouw account ingericht in Infisical.</span>}</label>;
  }
  return {View,Settings};
}
