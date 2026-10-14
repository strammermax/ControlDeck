"use client";
import {useEffect,useState} from "react";
import {LinkwardenModule} from "./view";
import {linkwardenRequest} from "../../lib/linkwarden";
import {collectionSetting} from "./settings";
import type {ModuleViewProps,ModuleSettingsProps} from "../contracts";

export function View({settings,csrfToken}:ModuleViewProps) {
  return <LinkwardenModule key={settings.collectionId ?? "all"} csrfToken={csrfToken} compact collectionId={settings.collectionId ?? null}/>;
}

export function Settings({settings,csrfToken,onChange}:ModuleSettingsProps) {
  const value=settings.collectionId ?? null;
  const [collections,setCollections]=useState<{id:number;name:string}[]>([]);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(true);
  useEffect(()=>{let active=true;
    linkwardenRequest<{collections:{id:number;name:string}[]}>("/collections",csrfToken).then(result=>{if(active)setCollections(result.collections);}).catch(()=>{if(active)setError("Collecties niet beschikbaar. Controleer je Linkwarden-koppeling bij Bookmarks.");}).finally(()=>{if(active)setLoading(false);});
    return ()=>{active=false;};
  },[csrfToken]);
  return <div><label>Collectie<select value={value ?? ""} disabled={loading} onChange={event=>onChange({collectionId:collectionSetting(event.target.value)})}><option value="">Alle toegankelijke collecties</option>{value!==null&&!collections.some(item=>item.id===value)&&<option value={value}>Opgeslagen collectie (niet beschikbaar)</option>}{collections.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label>{loading&&<p role="status">Collecties laden…</p>}{error&&<p role="status">{error}</p>}</div>;
}
