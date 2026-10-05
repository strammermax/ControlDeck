"use client";
import {useEffect,useState} from "react";
import {installationRequest,type InstallPlan,type InstallSelection} from "../lib/installations";
import {ProxmoxConnect} from "./proxmox-connect";
import {ProxmenuxConnect} from "./proxmenux-connect";

type Catalog={modules:{id:string;name:string;kind:"install"|"connect";description:string;version:string;resources?:{cpu:number;memoryMb:number}}[];status:{workerAvailable:boolean;configured:boolean;online:boolean};connections?:Record<string,boolean>};
type Job={id:string;status:"queued"|"running"|"succeeded"|"failed";message?:string};
export function ModuleWizard({csrfToken}:{csrfToken:string}) {
  const [catalog,setCatalog]=useState<Catalog|null>(null);
  const [step,setStep]=useState(1);
  const [selection,setSelection]=useState<InstallSelection>({module:"termix",method:"docker",target:"local"});
  const [plan,setPlan]=useState<InstallPlan|null>(null);
  const [job,setJob]=useState<Job|null>(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [retry,setRetry]=useState(0);
  useEffect(()=>{let cancelled=false;installationRequest<Catalog>("",csrfToken).then(data=>{if(!cancelled){setCatalog(data);setError("");}}).catch(error=>{if(!cancelled)setError(error.message);});return()=>{cancelled=true;};},[csrfToken,retry]);
  useEffect(()=>{
    if(!job || !["queued","running"].includes(job.status))return;
    let cancelled=false;
    const timer=setInterval(()=>{installationRequest<Job>(`/jobs/${job.id}`,csrfToken).then(data=>{if(!cancelled){setJob(data);setError("");}}).catch(error=>{if(!cancelled)setError(error.message);});},2500);
    return()=>{cancelled=true;clearInterval(timer);};
  },[job,csrfToken]);
  const review=async()=>{setBusy(true);setError("");try{setPlan(await installationRequest<InstallPlan>("/plan",csrfToken,selection));setStep(4);}catch(error){setError(error instanceof Error ? error.message : "Plan niet beschikbaar.");}finally{setBusy(false);}};
  const install=async()=>{setBusy(true);setError("");try{setJob(await installationRequest<Job>("/jobs",csrfToken,selection));setStep(5);}catch(error){setError(error instanceof Error ? error.message : "Installatie niet beschikbaar.");}finally{setBusy(false);}};
  const kind=catalog?.modules.find(module=>module.id===selection.module)?.kind;
  if(kind==="connect" && step>1) return <section className="module-wizard"><h3>Module koppelen</h3><p>Koppel een bestaande toepassing aan ControlDeck. Alleen-lezen; ControlDeck voert geen acties uit.</p>{selection.module==="proxmenux" ? <ProxmenuxConnect csrfToken={csrfToken} onBack={()=>setStep(1)}/> : <ProxmoxConnect csrfToken={csrfToken} onBack={()=>setStep(1)}/>}</section>;
  return <section className="module-wizard"><h3>Module installeren</h3><p>Voeg een toepassing toe aan ControlDeck. De wizard controleert de bestemming en koppelt de module na installatie.</p>
    <ol className="wizard-progress" aria-label="Installatiestappen">{["Module","Docker of LXC","Bestemming","Controleren","Installeren"].map((label,index)=><li key={label} aria-current={step===index+1 ? "step" : undefined}>{index+1}. {label}</li>)}</ol>
    {error && <p role="alert">{error}</p>}
    {!catalog ? <><p role="status">{error ? "De modulecatalogus kan niet worden geladen." : "Modulecatalogus laden…"}</p>{error && <button onClick={()=>setRetry(retry+1)}>Opnieuw proberen</button>}</> : <>
      {step===1 && <fieldset><legend>Kies een module</legend>{catalog.modules.map(module=><label className="wizard-choice" key={module.id}><input type="radio" name="module" checked={selection.module===module.id} onChange={()=>setSelection({...selection,module:module.id})}/><span><strong>{module.name}</strong> · {module.version}<br/>{module.description}<br/><small>{module.kind==="connect" ? (catalog.connections?.[module.id] ? "Gekoppeld. Kies Volgende om de koppeling te vervangen." : "Klaar om te koppelen.") : catalog.status.online && catalog.status.configured ? "Termix is al geïnstalleerd en gekoppeld." : "Klaar om te installeren."}</small></span></label>)}</fieldset>}
      {step===2 && <fieldset><legend>Hoe wil je de module installeren?</legend><label className="wizard-choice"><input type="radio" name="method" checked={selection.method==="docker"} onChange={()=>setSelection({...selection,method:"docker",target:"local"})}/><span><strong>Docker</strong><br/>Een aparte container op de ControlDeck-host.</span></label><label className="wizard-choice"><input type="radio" name="method" checked={selection.method==="lxc"} onChange={()=>setSelection({...selection,method:"lxc",target:"proxmox"})}/><span><strong>Proxmox LXC</strong><br/>Automatisch een nieuwe container aanmaken via Proxmox VE Helper-Scripts.</span></label></fieldset>}
      {step===3 && <fieldset><legend>Bestemming en instellingen</legend><label>Bestemming<select value={selection.target} onChange={()=>{}}><option value={selection.target}>{selection.method==="docker" ? "Deze ControlDeck-host" : "Proxmox"}</option></select></label><p>{selection.method==="docker" ? "Termix krijgt maximaal 1 CPU en 512 MB geheugen, met een apart opslagvolume." : "Het Helper-Script gebruikt standaard 4 CPU’s, 4096 MB geheugen en 10 GB schijf, onder meer voor het bouwen van Termix."}</p><p>De module gebruikt je ControlDeck-login en wordt geopend onder Terminal.</p>{selection.method==="lxc" && <p role="status">De Proxmox-verbinding is nog niet ingericht. De volgende stap toont wat er ontbreekt.</p>}</fieldset>}
      {step===4 && plan && <section><h4>Controleer je installatie</h4><dl><dt>Module</dt><dd>Termix</dd><dt>Methode</dt><dd>{plan.method==="docker" ? "Docker" : "Proxmox LXC · Helper-Scripts"}</dd><dt>Bestemming</dt><dd>{plan.target==="local" ? "Deze ControlDeck-host" : "Proxmox"}</dd><dt>Geheugen</dt><dd>{plan.resources.memoryMb} MB</dd></dl>{plan.alreadyInstalled && <p>Termix draait al. We controleren de installatie en herstellen de koppeling; bestaande gegevens blijven behouden.</p>}<ol>{plan.steps.map(item=><li key={item}>{item}</li>)}</ol>{plan.blockers.map(reason=><p role="alert" key={reason}>{reason}</p>)}</section>}
      {step===5 && job && <section aria-live="polite"><h4>{job.status==="succeeded" ? "Module gereed" : job.status==="failed" ? "Installatie niet afgerond" : "Installatie wordt uitgevoerd"}</h4><p>{job.message ?? "De installatieservice start binnenkort."}</p>{job.status==="succeeded" && <a className="provider-open" href="#terminal">Open Terminal →</a>}{job.status==="failed" && <button onClick={()=>{setStep(4);setJob(null);}}>Terug naar controle</button>}</section>}
      <div className="wizard-actions">{step>1 && step<5 && <button disabled={busy} onClick={()=>setStep(step-1)}>Vorige</button>}{step<3 && <button onClick={()=>setStep(step+1)}>Volgende</button>}{step===3 && <button disabled={busy} onClick={()=>void review()}>{busy ? "Controleren…" : "Installatie controleren"}</button>}{step===4 && <button disabled={busy || !plan?.canInstall} onClick={()=>void install()}>{busy ? "Klaarzetten…" : plan?.alreadyInstalled ? "Controleren en koppelen" : "Module installeren"}</button>}</div>
    </>}
  </section>;
}
