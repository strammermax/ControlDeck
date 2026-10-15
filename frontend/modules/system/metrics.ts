export const metricLabels = {cpu:"CPU-gebruik",memory:"Geheugen",temperature:"Temperatuur",power:"CPU-vermogen"} as const;
export type Metric = keyof typeof metricLabels;
export type MetricRow = {name:string;value:number|null;detail:string;stale:boolean;unavailable:boolean};
export function metricSetting(value:unknown):Metric {
  if(typeof value!=="string" || !Object.hasOwn(metricLabels,value))throw new Error("Kies een geldige systeemmeting.");
  return value as Metric;
}
export function metricEndpoint(metric:Metric) {
  return metric==="cpu"||metric==="memory" ? "/api/proxmox/summary" : "/api/proxmenux/summary";
}
function finite(value:unknown):number|null {return typeof value==="number"&&Number.isFinite(value)&&value>=0 ? value : null;}

/** Normalize only the selected measurement; unknown values never become zero or healthy. */
export function metricRows(metric:Metric,payload:unknown,node=""):MetricRow[] {
  if(!payload || typeof payload!=="object")throw new Error("Geen geldige systeemgegevens ontvangen.");
  const body=payload as Record<string,unknown>;
  const cluster=metric==="cpu"||metric==="memory";
  const summary=body.summary as Record<string,unknown>|undefined;
  const items=cluster ? summary?.[metric==="cpu"?"nodesByCpu":"nodesByMemory"] : body.nodes;
  if(!Array.isArray(items)||items.length>16)throw new Error("Geen geldige systeemgegevens ontvangen.");
  return items.map((item):MetricRow=>{
    if(!item || typeof item!=="object" || typeof item.name!=="string" || !item.name || item.name.length>128)throw new Error("Geen geldige nodegegevens ontvangen.");
    const offline=cluster&&Array.isArray(summary?.offlineNodes)&&summary.offlineNodes.includes(item.name);
    const raw=finite(item[metric==="power"?"powerWatts":metric]);
    const unavailable=Boolean(offline||item.loading);
    const value=unavailable||((metric==="cpu"||metric==="memory")&&raw!==null&&raw>100) ? null : raw;
    return {name:item.name,value,unavailable,stale:Boolean(body.stale||item.stale||item.error),detail:offline?"Offline":item.loading?"Wordt opgehaald":item.error?"Bron niet beschikbaar":item.partial?.length?"Gedeeltelijke brongegevens":value===null?"Geen meting beschikbaar":""};
  }).filter(item=>!node||item.name===node).sort((a,b)=>a.name.localeCompare(b.name));
}

export class MetricSourceError extends Error {
  denied:boolean;
  constructor(message:string,denied=false){super(message);this.denied=denied;}
}
/** Fixed API routes, session authentication and safe errors; no browser-selected upstream URL. */
export async function loadMetric(metric:Metric,node:string,signal:AbortSignal,request:typeof fetch=fetch) {
  let response:Response;
  try {response=await request(metricEndpoint(metric),{cache:"no-store",signal});}
  catch {throw new MetricSourceError("Systeemgegevens zijn tijdelijk niet bereikbaar.");}
  if(response.status===401||response.status===403)throw new MetricSourceError("Je hebt geen toegang tot deze systeemgegevens.",true);
  if(response.status===409)throw new MetricSourceError("Stel eerst de koppeling in bij Proxmox.");
  if(!response.ok)throw new MetricSourceError("Systeemgegevens zijn tijdelijk niet beschikbaar.");
  try {return metricRows(metric,await response.json(),node);}
  catch {throw new MetricSourceError("Geen geldige systeemgegevens ontvangen.");}
}
