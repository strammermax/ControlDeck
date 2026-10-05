export type Integration = {id:number;type:string;name:string;group:string;url:string;appUrl:string;showApp:boolean;authMode:string;linkId?:number|null;summary:{label:string;value:number}[]};
export type IntegrationKind = {type:string;name:string;icon:string;authModes:string[];capabilities:string[]};
export function integrationTiles(items:Integration[]) {
  return items.filter(item=>item.showApp&&!item.linkId).map(item=>({id:item.id,name:item.name,url:item.appUrl,collection:item.group,icon:item.type==='seerr'?'jellyseerr':item.type,description:item.summary.map(stat=>`${stat.label}: ${stat.value}`).join(' · '),tags:[]}));
}
export async function integrationRequest<T>(path:string,csrf:string,method='GET',body?:unknown):Promise<T> {
  const response=await fetch('/api/homepage/integrations'+path,{method,cache:'no-store',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:body===undefined?undefined:JSON.stringify(body)});
  const value=await response.json();
  if(!response.ok)throw new Error(value.error||'Integratie niet beschikbaar.');
  return value as T;
}

/** Settings pages are ordinary links; API credentials are never part of their URL. */
export function apiKeySettingsUrl(type:string,value:string):string|null {
  const paths:Record<string,string>={jellyfin:'/web/index.html#/dashboard/keys',seerr:'/settings/general'};
  if(!paths[type]||typeof value!=='string'||!value)return null;
  try {const url=new URL(value);if(!['http:','https:'].includes(url.protocol)||url.username||url.password||url.search||url.hash)return null;return value.replace(/\/+$/,'')+paths[type];}catch{return null;}
}

export function integrationCredentialsReady(form:{authMode:string;apiKey:string;username:string;password:string}):boolean {
  return form.authMode==='apiKey'?typeof form.apiKey==='string'&&form.apiKey.trim().length>0:
    form.authMode==='password'&&typeof form.username==='string'&&form.username.trim().length>0&&typeof form.password==='string'&&form.password.length>0;
}
