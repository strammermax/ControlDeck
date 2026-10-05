"use client";
import {useEffect,useState} from 'react';
import type {Bookmark} from '../lib/linkwarden';
import {BookmarkGroups} from './bookmark-groups';
import {HomepageIntegrations} from './homepage-integrations';
import {HomepageAppPicker} from './homepage-app-picker';
import type {AppChoice} from '../lib/homepage-apps';

type HomeLink=Bookmark&{icon?:string};
const blank={name:'',url:'',collection:'',description:'',icon:''};
export function HomepageLinks({csrfToken,isAdmin}:{csrfToken:string;isAdmin:boolean}) {
  const [picking,setPicking]=useState(false);
  const [selectedApp,setSelectedApp]=useState<AppChoice|null>(null);
  const [integrationType,setIntegrationType]=useState<string|null>(null);
  const [integrationReload,setIntegrationReload]=useState(0);
  const [links,setLinks]=useState<HomeLink[]>([]);
  const [query,setQuery]=useState('');
  const [error,setError]=useState('');
  const [loading,setLoading]=useState(true);
  const [editing,setEditing]=useState<number|null>(null);
  const [form,setForm]=useState(blank);
  const [settings,setSettings]=useState(false);
  const [busy,setBusy]=useState(false);
  const [reload,setReload]=useState(0);
  useEffect(()=>{let cancelled=false;setLoading(true);setError('');
    fetch('/api/homepage/links',{cache:'no-store'}).then(async response=>{const value=await response.json();if(!response.ok)throw new Error(value.error||'Homepage is niet beschikbaar.');if(!cancelled)setLinks(value.links);}).catch(failure=>{if(!cancelled)setError(failure.message);}).finally(()=>{if(!cancelled)setLoading(false);});
    return()=>{cancelled=true;};
  },[reload]);
  const filtered=links.filter(item=>`${item.name} ${item.description} ${item.collection} ${item.url}`.toLowerCase().includes(query.toLowerCase()));
  const mutate=async(method:string,id?:number)=>{setBusy(true);setError('');try{const response=await fetch('/api/homepage/links'+(id?`/${id}`:''),{method,headers:{'Content-Type':'application/json','X-CSRF-Token':csrfToken},body:method==='DELETE'?undefined:JSON.stringify(form)});const value=await response.json();if(!response.ok)throw new Error(value.error);setLinks(value.links);setSettings(false);setEditing(null);setForm(blank);}catch(failure){setError(failure instanceof Error?failure.message:'Niet beschikbaar.');}finally{setBusy(false);}};
  return <section className="homepage-bookmarks" aria-labelledby="homepage-heading"><div className="bookmark-section-heading"><div><h3 id="homepage-heading">Homepage</h3><p>Je toepassingen en links, beheerd in ControlDeck.</p></div><div><button onClick={()=>setReload(value=>value+1)} disabled={loading}>Vernieuwen</button>{isAdmin&&<button onClick={()=>{setSettings(true);setEditing(null);setForm(blank);setPicking(true);setSelectedApp(null);setIntegrationType(null);}}>Link toevoegen</button>}</div></div>
    {settings&&isAdmin&&picking&&<HomepageAppPicker onCancel={()=>setSettings(false)} onSelect={app=>{setSelectedApp(app);setForm({...blank,name:app?.name||'',icon:app?.icon||''});setPicking(false);}}/>}
    {settings&&isAdmin&&integrationType&&<HomepageIntegrations csrfToken={csrfToken} isAdmin={isAdmin} editorOnly initialType={integrationType} initialValues={form} onFinish={()=>{setSettings(false);setIntegrationType(null);setIntegrationReload(value=>value+1);}}/>}
    {settings&&isAdmin&&!picking&&!integrationType&&<form className="bookmark-form" onSubmit={event=>{event.preventDefault();void mutate(editing?'PUT':'POST',editing??undefined);}}><h4>{editing?'Link aanpassen':'Nieuwe Homepage-link'}</h4>{!editing&&<div className="form-actions"><button type="button" onClick={()=>setPicking(true)}>Andere app kiezen</button>{selectedApp?.apiSupported&&<button type="button" onClick={()=>setIntegrationType(selectedApp.id)}>Link met API-koppeling instellen</button>}</div>}{selectedApp?.port&&<p>Gebruik je eigen adres; de gebruikelijke poort voor {selectedApp.name} is {selectedApp.port}.</p>}{([['name','Titel',300],['url','Adres',2048],['collection','Groep',200],['description','Beschrijving (optioneel)',1000],['icon','Icoon (optioneel, anders automatisch)',100]] as const).map(([key,label,max])=><label key={key}>{label}<input required={['name','url','collection'].includes(key)} type={key==='url'?'url':'text'} maxLength={max} value={form[key]} onChange={event=>setForm(value=>({...value,[key]:event.target.value}))} list={key==='collection'?'homepage-groups':undefined}/></label>)}<datalist id="homepage-groups">{[...new Set(links.map(item=>item.collection))].map(name=><option value={name} key={name}/>)}</datalist><div className="form-actions"><button disabled={busy}>Bewaren</button><button type="button" onClick={()=>setSettings(false)}>Annuleren</button>{editing&&<button type="button" disabled={busy} onClick={()=>{if(window.confirm('Deze link uit Homepage verwijderen?'))void mutate('DELETE',editing);}}>Link verwijderen</button>}</div></form>}
    {error&&<p role="alert" className="config-error">{error}</p>}{loading&&<p role="status">Homepage laden…</p>}
    {!loading&&!error&&<><label className="homepage-search">Zoeken in Homepage<input type="search" value={query} onChange={event=>setQuery(event.target.value)} maxLength={200} placeholder="Zoek een toepassing of groep"/></label>{filtered.length===0?<p>Geen Homepage-links gevonden.{isAdmin?' Voeg je eerste link toe om een groep te maken.':''}</p>:<BookmarkGroups links={filtered} onEdit={isAdmin?item=>{setForm({name:item.name,url:item.url,collection:item.collection,description:item.description,icon:item.icon||''});setEditing(item.id);setSettings(true);setPicking(false);setSelectedApp(null);setIntegrationType(null);}:undefined}/>}</>}
    {!integrationType&&<HomepageIntegrations key={integrationReload} csrfToken={csrfToken} isAdmin={isAdmin}/>}
  </section>;
}
