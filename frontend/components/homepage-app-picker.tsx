"use client";
import {useState} from 'react';
import {searchApps,homepageApps,type AppChoice} from '../lib/homepage-apps';
import icons from '../lib/service-icons.json';
export function HomepageAppPicker({onSelect,onCancel}:{onSelect:(app:AppChoice|null)=>void;onCancel:()=>void}) {
  const [query,setQuery]=useState('');
  const apps=searchApps(query);
  return <section className="homepage-app-picker" aria-label="Toepassing kiezen"><h4>Kies een toepassing</h4><label>Apps zoeken<input type="search" value={query} maxLength={100} onChange={event=>setQuery(event.target.value)} placeholder="Bijvoorbeeld Plex, Radarr of Jellyfin"/></label><button type="button" onClick={()=>onSelect(null)}>Eigen link</button><button type="button" onClick={onCancel}>Annuleren</button><div className="homepage-app-grid">{apps.map(app=><button type="button" key={app.id} onClick={()=>onSelect(app)}>{icons.includes(app.icon)?<img src={`/service-icons/${app.icon}.png`} width={32} height={32} alt=""/>:<span aria-hidden="true">{app.name.slice(0,2)}</span>}<strong>{app.name}</strong><small>{app.apiSupported?'Link + API beschikbaar':'Link toevoegen'}</small></button>)}</div>{apps.length===0&&<p>Geen toepassingen gevonden. Je kunt altijd een eigen link toevoegen.</p>}<p>{homepageApps.length} apps uit de Homarr-catalogus. API-koppelingen zijn beschikbaar waar een ControlDeck-adapter is toegevoegd.</p></section>;
}
