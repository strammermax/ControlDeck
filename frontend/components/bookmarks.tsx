"use client";
import {useEffect,useState} from 'react';
import {linkwardenRequest,type BookmarkPage} from '../lib/linkwarden';
import {groupBookmarks} from '../lib/bookmark-layout';
import {BookmarkGroups} from './bookmark-groups';
import {HomepageLinks} from './homepage-links';

/** Native UI, shared Google login, and personal Linkwarden API access. */
export function Bookmarks({csrfToken,isAdmin=false}:{csrfToken:string;isAdmin?:boolean}) {
  const [connection,setConnection]=useState<{connected:boolean;url:string}|null>(null);
  const [token,setToken]=useState('');
  const [settings,setSettings]=useState(false);
  const [query,setQuery]=useState('');
  const [collection,setCollection]=useState('');
  const [collections,setCollections]=useState<{id:number;name:string}[]>([]);
  const [page,setPage]=useState<BookmarkPage>({links:[],nextCursor:null});
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  const [loaded,setLoaded]=useState(false);
  const [adding,setAdding]=useState(false);
  const [url,setUrl]=useState('');
  const [name,setName]=useState('');
  const [newCollection,setNewCollection]=useState('');
  const [reload,setReload]=useState(0);
  useEffect(()=>{let cancelled=false;setError('');setLoaded(false);
    linkwardenRequest<{connected:boolean;url:string}>('/token',csrfToken).then(async value=>{
      if(cancelled)return;setConnection(value);
      if(value.connected){const [links,groups]=await Promise.all([linkwardenRequest<BookmarkPage>('/bookmarks',csrfToken),linkwardenRequest<{collections:{id:number;name:string}[]}>('/collections',csrfToken)]);
        if(!cancelled){setPage(links);setCollections(groups.collections);setLoaded(true);}}
    }).catch(failure=>{if(!cancelled)setError(failure.message);});return()=>{cancelled=true;};
  },[csrfToken,reload]);
  const search=async(more=false)=>{setBusy(true);setError('');try{const params=new URLSearchParams({query});if(collection)params.set('collection',collection);if(more&&page.nextCursor)params.set('cursor',String(page.nextCursor));const result=await linkwardenRequest<BookmarkPage>(`/bookmarks?${params}`,csrfToken);setPage(more ? {links:[...page.links,...result.links],nextCursor:result.nextCursor} : result);setLoaded(true);}catch(failure){setError(failure instanceof Error?failure.message:'Niet beschikbaar.');}finally{setBusy(false);}};
  const groups=groupBookmarks(page.links);
  return <section className="bookmarks-panel">
    <HomepageLinks csrfToken={csrfToken} isAdmin={isAdmin}/>
    <section className="linkwarden-bookmarks" aria-labelledby="linkwarden-heading"><h3 id="linkwarden-heading" className="bookmark-section-title">Linkwarden</h3>
    <div className="terminal-toolbar"><span>Je startpagina · Bookmarks uit Linkwarden</span><div>{connection?.url&&<a href={`${connection.url}/dashboard`} target="_blank" rel="noopener noreferrer">Open Linkwarden ↗</a>} <button onClick={()=>setSettings(!settings)}>Mijn koppeling</button></div></div>
    <p className="bookmark-hint">Bookmarks die je met de Linkwarden-browserextensie bewaart, verschijnen hier na vernieuwen. Je ziet je eigen collecties en de collecties die met jou zijn gedeeld.</p>
    {error&&<p role="alert" className="config-error">{error}</p>}
    {(settings||connection?.connected===false)&&<form className="bookmark-form" onSubmit={async event=>{event.preventDefault();setBusy(true);setError('');try{await linkwardenRequest('/token',csrfToken,'PUT',{token});setToken('');setSettings(false);setReload(reload+1);}catch(failure){setError(failure instanceof Error?failure.message:'Niet beschikbaar.');}finally{setBusy(false);}}}>
      <h3>Persoonlijke Linkwarden-koppeling</h3><p>Maak in Linkwarden onder instellingen een API-token van je eigen account. Het e-mailadres moet overeenkomen met je ControlDeck-account. Je token blijft op de server opgeslagen en wordt niet teruggestuurd.</p>
      <label>API-token<input type="password" autoComplete="off" value={token} onChange={event=>setToken(event.target.value)} required minLength={20} maxLength={4096}/></label>
      <div className="form-actions"><button disabled={busy||!token} type="submit">Controleren en koppelen</button>{connection?.connected&&<button disabled={busy} type="button" onClick={async()=>{try{await linkwardenRequest('/token',csrfToken,'DELETE');setPage({links:[],nextCursor:null});setReload(reload+1);}catch(failure){setError(failure instanceof Error?failure.message:'Niet beschikbaar.');}}}>Mijn koppeling verwijderen</button>}</div>
    </form>}
    {connection?.connected&&<>
      <form className="bookmark-search" onSubmit={event=>{event.preventDefault();void search();}}><label>Zoeken<input value={query} maxLength={200} onChange={event=>setQuery(event.target.value)} placeholder="Titel, adres of tag"/></label><label>Collectie<select value={collection} onChange={event=>setCollection(event.target.value)}><option value="">Alle collecties</option>{collections.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label><button disabled={busy}>Zoeken</button><button disabled={busy} type="button" onClick={()=>void search()}>Vernieuwen</button><button type="button" onClick={()=>setAdding(!adding)}>Bookmark toevoegen</button></form>
      {adding&&<form className="bookmark-form" onSubmit={async event=>{event.preventDefault();setBusy(true);setError('');try{await linkwardenRequest('/bookmarks',csrfToken,'POST',{url,name,collectionId:Number(newCollection)});setAdding(false);setUrl('');setName('');await search();}catch(failure){setError(failure instanceof Error?failure.message:'Niet beschikbaar.');}finally{setBusy(false);}}}><label>Adres<input type="url" required value={url} onChange={event=>setUrl(event.target.value)} maxLength={2048}/></label><label>Titel<input value={name} onChange={event=>setName(event.target.value)} maxLength={300}/></label><label>Collectie<select required value={newCollection} onChange={event=>setNewCollection(event.target.value)}><option value="">Kies een collectie</option>{collections.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label><button disabled={busy} type="submit">Bewaren in Linkwarden</button></form>}
      {!loaded&&!error&&<p role="status">Bookmarks laden…</p>}
      {loaded&&page.links.length===0&&<p>Geen bookmarks gevonden.</p>}
      {loaded&&groups.length>0&&<p className="bookmark-overview" role="status">{groups.reduce((count,group)=>count+group.links.length,0)} bookmarks · {groups.length} collecties{page.nextCursor?' · Meer beschikbaar':''}</p>}
      <BookmarkGroups links={page.links}/>
      {page.nextCursor&&<button disabled={busy} onClick={()=>void search(true)}>Meer laden</button>}
    </>}
    </section>
  </section>;
}
