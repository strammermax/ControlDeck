export const serviceWidgets = [
  {id:"downloads",title:"Downloads",description:"qBittorrent- en SABnzbd-wachtrijen",permission:"media",width:6,height:5,settings:{sourceId:""}},
  {id:"media-widget",title:"Media",description:"Plex-streams en Seerr-aanvragen",permission:"media",width:6,height:5,settings:{sourceId:""}},
  {id:"tdarr",title:"Tdarr",description:"Workers en verwerking",permission:"media",width:6,height:5,settings:{sourceId:""}},
  {id:"homeassistant-dashboard",title:"Home Assistant",description:"Toon een dashboard uit Home Assistant",permission:"monitoring",width:12,height:6,settings:{sourceId:""}},
  {id:"calendar",title:"Agenda",description:"Komende afspraken uit Nextcloud",permission:"files",width:6,height:5,settings:{sourceId:""}},
  {id:"statistics",title:"Flows en aanbiedingen",description:"Prefect-flowruns of nieuwste Koopjesbot-aanbiedingen",permission:"monitoring",width:6,height:5,settings:{sourceId:""}},
] as const;
export type ServiceFamily = typeof serviceWidgets[number]["id"];
export type WidgetSource = {id:string;title:string;kind:string};
export function validateWidgetSources(value:unknown):WidgetSource[] {
  const rows=(value as {sources?:unknown}|null)?.sources;
  if(!Array.isArray(rows)||rows.length>64||rows.some(row=>!row||typeof row.id!=="string"||!/^[a-z0-9-]{1,64}$/.test(row.id)||typeof row.title!=="string"||row.title.length>100||typeof row.kind!=="string"||row.kind.length>64))throw new WidgetError("Ongeldige widgetbronnen.");
  if(new Set(rows.map(row=>row.id)).size!==rows.length)throw new WidgetError("Dubbele widgetbron.");
  return rows;
}
export type WidgetData = {items:{id:string;title:string;subtitle:string;status:string;progress?:number;date?:string;allDay?:boolean;url?:string;priceCents?:number|null;currency?:string}[];stats:{label:string;value:string}[];updatedAt:number|null;stale:boolean;pending?:boolean;truncated?:boolean;embedUrl?:string;title?:string;sourceTitle?:string};
export class WidgetError extends Error {
  denied:boolean;
  constructor(message:string,denied=false){super(message);this.denied=denied;}
}
export function widgetPath(family:ServiceFamily,sourceId:string) {
  if(!serviceWidgets.some(w=>w.id===family)||! /^[a-z0-9-]{1,64}$/.test(sourceId))throw new WidgetError("Kies een geldige widgetbron.");
  return `/api/widgets/${family}/${sourceId}`;
}
export function safeEmbed(value:unknown):string {
  if(typeof value!=="string")throw new WidgetError("Ongeldig dashboardadres.");
  const url=new URL(value);
  if(url.protocol!=="https:"||url.username||url.password||url.search||url.hash)throw new WidgetError("Ongeldig dashboardadres.");
  return url.href;
}
export function offerLink(value:string) {
  const url=new URL(value);
  if(!["https:","http:"].includes(url.protocol)||url.username||url.password)throw new WidgetError("Ongeldige advertentielink.");
  return url.href;
}
export async function widgetRequest<T>(path:string,signal:AbortSignal,request:typeof fetch=fetch):Promise<T> {
  let response:Response;
  try{response=await request(path,{cache:"no-store",signal});}catch{throw new WidgetError("De widgetbron is niet bereikbaar.");}
  if(!response.ok)throw new WidgetError(response.status===401||response.status===403||response.status===404?"Je hebt geen toegang tot deze bron of deze is verwijderd.":"Widgetgegevens zijn niet beschikbaar. Controleer de koppeling.",[401,403,404].includes(response.status));
  try{return await response.json() as T;}catch{throw new WidgetError("Ongeldig antwoord van de widgetbron.");}
}
export function widgetDate(value:string,allDay=false) {
  const date=new Date(allDay?`${value}T12:00:00`:value);
  return Number.isNaN(date.valueOf())?"Tijdstip onbekend":date.toLocaleString("nl-NL",allDay?{dateStyle:"medium"}:{dateStyle:"medium",timeStyle:"short"});
}

/** Validate normalized display data before mounting React, including empty and iframe responses. */
export function validateWidgetData(value:unknown):WidgetData {
  if(!value||typeof value!=="object")throw new WidgetError("Ongeldige widgetgegevens.");
  const data=value as WidgetData;
  if(data.embedUrl)return {items:[],stats:[],updatedAt:null,stale:false,embedUrl:safeEmbed(data.embedUrl),title:typeof data.title==="string"?data.title.slice(0,100):"Home Assistant",sourceTitle:typeof data.sourceTitle==="string"?data.sourceTitle.slice(0,100):""};
  if(!Array.isArray(data.items)||data.items.length>50||!Array.isArray(data.stats)||data.stats.length>20||typeof data.stale!=="boolean"||(data.updatedAt!==null&&(typeof data.updatedAt!=="number"||!Number.isFinite(data.updatedAt)||data.updatedAt<0||data.updatedAt>1e11)))throw new WidgetError("Ongeldige widgetgegevens.");
  for(const row of data.items){
    if(!row||[row.id,row.title,row.subtitle,row.status].some(v=>typeof v!=="string"||v.length>300))throw new WidgetError("Ongeldige widgetregel.");
    if(row.progress!==undefined&&(typeof row.progress!=="number"||!Number.isFinite(row.progress)||row.progress<0||row.progress>100))throw new WidgetError("Ongeldige voortgang.");
    if(row.url!==undefined)offerLink(row.url);
    if(row.priceCents!==undefined&&row.priceCents!==null&&(!Number.isSafeInteger(row.priceCents)||row.priceCents<0||row.priceCents>1e12))throw new WidgetError("Ongeldige prijs.");
    if(row.currency!==undefined&&!/^[A-Z]{3}$/.test(row.currency))throw new WidgetError("Ongeldige valuta.");
    if(row.date!==undefined&&(typeof row.date!=="string"||row.date.length>80))throw new WidgetError("Ongeldig tijdstip.");
  }
  if(data.stats.some(row=>!row||typeof row.label!=="string"||row.label.length>100||typeof row.value!=="string"||row.value.length>4096))throw new WidgetError("Ongeldige statistieken.");
  return data;
}
