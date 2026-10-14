"use client";
import {useEffect,useState} from "react";
import {LinkwardenModule} from "./linkwarden-module";
import {linkwardenRequest} from "../lib/linkwarden";
import {collectionSetting} from "../lib/dashboard-modules";

export function DashboardModule({moduleId,collectionId,csrfToken,allowed}:{moduleId:string;collectionId:number|null;csrfToken:string;allowed:boolean}) {
  if(!allowed) return <p className="cd-dashboard-unavailable">Je hebt geen toegang tot deze module.</p>;
  if(moduleId!=="linkwarden") return <p>Deze module is niet beschikbaar.</p>;
  return <div className="cd-dashboard-module"><header><strong>Linkwarden</strong></header><LinkwardenModule key={collectionId ?? "all"} csrfToken={csrfToken} compact collectionId={collectionId}/></div>;
}

export function LinkwardenCollectionPicker({value,csrfToken,onChange}:{value:number|null;csrfToken:string;onChange:(value:number|null)=>void}) {
  const [collections,setCollections]=useState<{id:number;name:string}[]>([]);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(true);
  useEffect(()=>{let active=true;
    linkwardenRequest<{collections:{id:number;name:string}[]}>("/collections",csrfToken).then(result=>{if(active)setCollections(result.collections);}).catch(()=>{if(active)setError("Collecties niet beschikbaar. Controleer je Linkwarden-koppeling bij Bookmarks.");}).finally(()=>{if(active)setLoading(false);});
    return ()=>{active=false;};
  },[csrfToken]);
  return <div><label>Collectie<select value={value ?? ""} disabled={loading} onChange={event=>onChange(collectionSetting(event.target.value))}><option value="">Alle toegankelijke collecties</option>{value!==null&&!collections.some(item=>item.id===value)&&<option value={value}>Opgeslagen collectie (niet beschikbaar)</option>}{collections.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label>{loading&&<p role="status">Collecties laden…</p>}{error&&<p role="status">{error}</p>}</div>;
}
