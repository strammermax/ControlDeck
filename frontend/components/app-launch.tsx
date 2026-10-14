"use client";
import {useState} from "react";
import {requestAppLaunch} from "../lib/app-launches";
export function AppLaunch({moduleId,title,csrfToken}:{moduleId:"kasm"|"nextcloud";title:string;csrfToken:string}) {
  const [busy,setBusy]=useState(false),[error,setError]=useState("");
  return <section className="cd-app-launch"><p>{moduleId==="kasm"?"Open je virtuele apps met je gekoppelde Kasm-account.":"Open Nextcloud via je bestaande Google-aanmelding."}</p>
    <button disabled={busy} onClick={async()=>{setBusy(true);setError("");try{const url=await requestAppLaunch(moduleId,csrfToken);window.location.assign(url);}catch(failure){setError(failure instanceof Error?failure.message:"Aanmelden mislukt.");setBusy(false);}}}>{busy?"Aanmelden…":`Open ${title}`}</button>
    {error&&<p role="alert">{error}</p>}
  </section>;
}
