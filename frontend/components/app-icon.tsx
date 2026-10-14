"use client";
import {useState} from "react";
import {websiteFavicon, uploadDashboardIcon} from "../lib/app-icons";
import {bookmarkIcon} from "../lib/bookmark-icons";

export function AppIcon({name,url,icon,size=28}:{name:string;url:string;icon?:string;size?:number}) {
  const [failed,setFailed]=useState<string[]>([]);
  const candidates=[icon?.startsWith("data:image/png;base64,")?icon:null,websiteFavicon(url),bookmarkIcon(name,url,icon)];
  const src=candidates.find(value=>value&&!failed.includes(value));
  return src?<img src={src} alt="" width={size} height={size} loading="lazy" referrerPolicy="no-referrer" onError={()=>setFailed(values=>[...values,src])}/>:<span aria-hidden="true">{Array.from(name)[0]?.toUpperCase()||"↗"}</span>;
}

export function AppIconPicker({value,onChange,onBusy}:{value:string;onChange:(icon:string)=>void;onBusy:(busy:boolean)=>void}) {
  const [error,setError]=useState("");
  return <div><label>Eigen PNG-icoon<input type="file" accept="image/png" onChange={async event=>{
    const file=event.target.files?.[0];if(!file)return;onBusy(true);setError("");
    try{onChange(await uploadDashboardIcon(file));}catch{setError("Kies een geldige PNG van maximaal 2 MB en 4096 × 4096 pixels.");}finally{onBusy(false);}
  }}/></label><p>Standaard gebruiken we het favicon van de website. Een eigen PNG vervangt dit.</p>
  {value.startsWith("data:image/png;base64,")&&<div><img src={value} alt="Eigen icoon" width={48} height={48}/><button type="button" onClick={()=>onChange("")}>Website-icoon gebruiken</button></div>}
  {error&&<p role="alert">{error}</p>}</div>;
}
