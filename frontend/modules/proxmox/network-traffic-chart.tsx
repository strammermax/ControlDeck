"use client";
/** Adapted from MacRimi/ProxMenux network-traffic-chart.tsx, GPL-3.0,
 * d4e98d16b11733e518b0162db1b528b2ecd4cc53. Recharts area/grid/axes/palette
 * retained; authenticated projection, aligned cluster data and accessible legend added.
 */
import {useEffect,useState,type ReactNode} from "react";
import {Area,AreaChart,CartesianGrid,ResponsiveContainer,Tooltip,XAxis,YAxis} from "recharts";
import {GuestIcon} from "./guest-cards";
import {trafficPeriods,trafficSeries,trafficTotals,trafficTick,validateTrafficHistory,type TrafficHistoryNode,type TrafficPeriod,type TrafficPoint} from "../../lib/proxmox-network-history";

export function TrafficTooltip({active,payload,label}:{active?:boolean;payload?:readonly {value?:unknown;name?:unknown;color?:string}[];label?:unknown}) {
 if(!active||!payload?.length)return null;
 return <div className="pm-traffic-tooltip"><strong>{typeof label==="number"?new Date(label*1000).toLocaleString("nl-NL"):"Network Traffic"}</strong>{payload.map((p,index)=><div key={index}><span style={{color:p.color}}>{typeof p.name==="string"?p.name:"Traffic"}</span><strong>{typeof p.value==="number"&&Number.isFinite(p.value)?`${p.value.toFixed(3)} GB`:"—"}</strong></div>)}</div>;
}
export function TrafficPlot({points,period}:{points:TrafficPoint[];period:TrafficPeriod}) {
 const [received,setReceived]=useState(true),[sent,setSent]=useState(true);
 return <><div className="pm-traffic-legend" role="group" aria-label="Verkeersreeksen"><button type="button" aria-pressed={received} aria-label="Received" onClick={()=>setReceived(v=>!v)}><i aria-hidden="true" style={{background:"#10b981"}}/>Received</button><button type="button" aria-pressed={sent} aria-label="Sent" onClick={()=>setSent(v=>!v)}><i aria-hidden="true" style={{background:"#3b82f6"}}/>Sent</button></div><div className="pm-traffic-chart" role="img" aria-label="Network Traffic, ontvangen en verzonden GB per meetinterval"><ResponsiveContainer width="100%" height={320} minWidth={0}><AreaChart data={points} margin={{top:8,right:12,left:12,bottom:40}}><CartesianGrid strokeDasharray="3 3" stroke="var(--border)"/><XAxis dataKey="time" type="number" domain={["dataMin","dataMax"]} tickFormatter={time=>trafficTick(Number(time),period)} stroke="var(--muted)" tick={{fill:"var(--text)",fontSize:12}} angle={-45} textAnchor="end" height={60} tickCount={8} minTickGap={30}/><YAxis stroke="var(--muted)" tick={{fill:"var(--text)",fontSize:12}} label={{value:"GB",angle:-90,position:"insideLeft",fill:"var(--text)"}} domain={[0,"auto"]}/><Tooltip content={<TrafficTooltip/>}/><Area type="monotone" dataKey="received" name="Received" stroke="#10b981" strokeWidth={2} fill="#10b981" fillOpacity={.3} hide={!received} connectNulls={false} isAnimationActive={false}/><Area type="monotone" dataKey="sent" name="Sent" stroke="#3b82f6" strokeWidth={2} fill="#3b82f6" fillOpacity={.3} hide={!sent} connectNulls={false} isAnimationActive={false}/></AreaChart></ResponsiveContainer></div></>;
}
export function NetworkTrafficChart({names,refreshSeconds=60,overview}:{names:string[];refreshSeconds?:number;overview?:(traffic:{received:number|null;sent:number|null;label:string})=>ReactNode}) {
 const [period,setPeriod]=useState<TrafficPeriod>("day"),[packet,setPacket]=useState<{period:TrafficPeriod;nodes:TrafficHistoryNode[]}|null>(null),[error,setError]=useState(""),[pending,setPending]=useState(false);
 useEffect(()=>{
  let active=true,busy=false;const controller=new AbortController();setError("");
  const load=async()=>{
   if(busy)return;busy=true;
   try{
    const response=await fetch(`/api/proxmenux/network/history?timeframe=${period}`,{cache:"no-store",signal:AbortSignal.any([controller.signal,AbortSignal.timeout(25000)])});
    if(!response.ok){if(active)setPacket(null);throw new Error([401,403].includes(response.status)?"Je hebt geen toegang tot de netwerkhistorie.":response.status===409?"Koppel eerst ProxMenux via Admin → Modules.":"Netwerkhistorie is niet beschikbaar.");}
    const nodes=validateTrafficHistory(await response.json(),period);
    if(active){setPacket({period,nodes});setPending(nodes.some(n=>n.loading));setError("");}
   }catch(failure){if(active){setError(failure instanceof Error?failure.message:"De netwerkhistorie kon niet worden geladen.");setPacket(null);}}
   finally{busy=false;}
  };
  void load();const timer=setInterval(()=>void load(),pending?5000:Math.max(30,refreshSeconds)*1000);
  return()=>{active=false;controller.abort();clearInterval(timer);};
 },[period,refreshSeconds,pending]);
 const sources=packet?.period===period?packet.nodes:[],series=trafficSeries(sources,names,period),hasValues=series.points.some(p=>p.received!==null||p.sent!==null);
 return <>{overview?.({...trafficTotals(series.points,series.incomplete),label:`${trafficPeriods[period]}${error?" · niet beschikbaar":sources.length===0||sources.some(n=>n.loading)?" · laden…":series.incomplete?" · onvolledig":""}`})}<section className="pm-card pm-traffic"><header className="pm-list-head"><h3><GuestIcon kind="activity"/>Network Traffic</h3><label className="pm-traffic-period">Periode <select aria-label="Periode netwerkverkeer" value={period} onChange={e=>setPeriod(e.target.value as TrafficPeriod)}>{Object.entries(trafficPeriods).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label></header><div className="pm-list-content">{error&&<p role="alert" className="config-error">{error}</p>}{!error&&(sources.length===0||sources.some(n=>n.loading))&&<p role="status">Netwerkhistorie laden…</p>}{!error&&series.incomplete&&sources.length>0&&<p role="status" className="pm-muted">Niet alle metingen zijn beschikbaar. Ontbrekende clusterwaarden blijven open in de grafiek.</p>}{hasValues?<TrafficPlot points={series.points} period={period}/>:!error&&!pending&&sources.length>0&&<p className="pm-traffic-empty">Geen volledige meetpunten voor deze selectie.</p>}<p className="pm-footnote">{series.step?`GB per meetinterval van ${series.step<3600?`${series.step/60} ${series.step===60?"minuut":"minuten"}`:`${series.step/3600} uur`}. `:""}Historische Proxmox-hostmetingen zoals in ProxMenux; cluster telt dezelfde tijdvakken op. Dit is geen uniek internetverbruik.</p></div></section></>;
}
