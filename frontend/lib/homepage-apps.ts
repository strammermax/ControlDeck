import data from './app-catalog.json' with {type:'json'};
export type AppChoice = {id:string;name:string;icon:string;port:number|null;categories:string[];apiSupported:boolean};
export const homepageApps:AppChoice[]=data.apps;
export function searchApps(query:string):AppChoice[] {
  if(typeof query!=='string')throw new TypeError('Ongeldige zoekterm');
  const words=query.toLowerCase().trim().split(/\s+/).filter(Boolean);
  return homepageApps.filter(app=>words.every(word=>`${app.name} ${app.categories.join(' ')}`.toLowerCase().includes(word)));
}
export function appDefaults(id:string) {
  const app=homepageApps.find(app=>app.id===id);
  if(!app)throw new Error('Onbekende toepassing');
  return {name:app.name,icon:app.icon,apiSupported:app.apiSupported,port:app.port};
}
