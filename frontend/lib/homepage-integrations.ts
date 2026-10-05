export type Integration = {id:number;type:string;name:string;group:string;url:string;appUrl:string;showApp:boolean;authMode:string;summary:{label:string;value:number}[]};
export type IntegrationKind = {type:string;name:string;icon:string;authModes:string[];capabilities:string[]};
export function integrationTiles(items:Integration[]) {
  return items.filter(item=>item.showApp).map(item=>({id:item.id,name:item.name,url:item.appUrl,collection:item.group,icon:item.type==='seerr'?'jellyseerr':item.type,description:item.summary.map(stat=>`${stat.label}: ${stat.value}`).join(' · '),tags:[]}));
}
export async function integrationRequest<T>(path:string,csrf:string,method='GET',body?:unknown):Promise<T> {
  const response=await fetch('/api/homepage/integrations'+path,{method,cache:'no-store',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:body===undefined?undefined:JSON.stringify(body)});
  const value=await response.json();
  if(!response.ok)throw new Error(value.error||'Integratie niet beschikbaar.');
  return value as T;
}
