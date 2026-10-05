"use client";
import {useEffect,useState} from "react";
import {installationRequest,modulesFor,type CatalogModule,type InstallPlan,type InstallSelection,type ManageTab} from "../lib/installations";
import {ProxmoxConnect} from "./proxmox-connect";
import {ProxmenuxConnect} from "./proxmenux-connect";
import {LinkwardenConnect} from "./linkwarden-connect";
import {CronjobsConnect} from "./cronjobs-connect";
import {ModuleRemove} from "./module-remove";
import {useJob,type Job} from "./use-job";

type Catalog={modules:CatalogModule[];status:{workerAvailable:boolean;workerOutdated?:boolean;configured:boolean;online:boolean}};
const TABS:{id:ManageTab;label:string;intro:string;empty:string}[]=[
  {id:"install",label:"Installeren",intro:"Voeg een toepassing toe aan ControlDeck. Alleen modules die nog niet zijn geïnstalleerd of gekoppeld staan hier.",empty:"Alle beschikbare modules zijn geïnstalleerd."},
  {id:"edit",label:"Bewerken",intro:"Pas de instellingen van een geïnstalleerde module aan.",empty:"Er zijn nog geen modules geïnstalleerd."},
  {id:"remove",label:"Verwijderen",intro:"Verwijder een module netjes. De wizard toont vooraf wat er gebeurt.",empty:"Er zijn nog geen modules geïnstalleerd."},
];

/** Admin → Modules: install, edit and remove modules. */
export function ModuleWizard({csrfToken}:{csrfToken:string}) {
  const [catalog,setCatalog]=useState<Catalog|null>(null);
  const [tab,setTab]=useState<ManageTab>("install");
  const [chosen,setChosen]=useState<string|null>(null);
  const [selected,setSelected]=useState<string>("");
  const [error,setError]=useState("");
  const [reload,setReload]=useState(0);
  useEffect(()=>{let cancelled=false;installationRequest<Catalog>("",csrfToken).then(data=>{if(!cancelled){setCatalog(data);setError("");}}).catch(failure=>{if(!cancelled)setError(failure.message);});return()=>{cancelled=true;};},[csrfToken,reload]);
  const visible=catalog ? modulesFor(tab,catalog.modules) : [];
  useEffect(()=>{ if(!visible.some(module=>module.id===selected)) setSelected(visible[0]?.id ?? ""); },[visible,selected]);
  const current=catalog?.modules.find(module=>module.id===chosen);
  const back=()=>{setChosen(null);setReload(reload+1);};
  const info=TABS.find(item=>item.id===tab)!;
  return <section className="module-wizard">
    <h3>Modulebeheer</h3>
    <div className="manage-tabs" role="tablist" aria-label="Modulebeheer">{TABS.map(item=><button key={item.id} role="tab" aria-selected={tab===item.id} className={tab===item.id ? "active" : undefined} onClick={()=>{setTab(item.id);setChosen(null);}}>{item.label}</button>)}</div>
    {error && <p role="alert">{error}</p>}
    {catalog?.status.workerOutdated && <div className="config-error" role="alert"><strong>Root-worker verouderd.</strong> Installeren werkt, maar nieuwere acties zoals Termix verwijderen zijn geblokkeerd. Werk de checkout bij en draai als root op de ControlDeck-host: <code>bash scripts/install-wizard.sh</code></div>}
    {!catalog ? <><p role="status">{error ? "De modulecatalogus kan niet worden geladen." : "Modulecatalogus laden…"}</p>{error && <button onClick={()=>setReload(reload+1)}>Opnieuw proberen</button>}</>
    : current ? (current.id==="linkwarden" ? <LinkwardenConnect csrfToken={csrfToken} onBack={back} remove={tab==="remove"}/> : tab==="remove" ? <ModuleRemove module={current} csrfToken={csrfToken} onDone={back}/>
      : current.id==="proxmox" ? <ProxmoxConnect csrfToken={csrfToken} onBack={back}/>
      : current.id==="proxmenux" ? <ProxmenuxConnect csrfToken={csrfToken} onBack={back}/>
      : current.id==="cronjobs" ? <CronjobsConnect csrfToken={csrfToken} onBack={back}/>
      : <TermixFlow csrfToken={csrfToken} repair={tab==="edit"} onBack={back}/>)
    : <>
      <p>{info.intro}</p>
      {visible.length ? <fieldset><legend>Kies een module</legend>{visible.map(module=><label className="wizard-choice" key={module.id}><input type="radio" name="module" checked={selected===module.id} onChange={()=>setSelected(module.id)}/><span><strong>{module.name}</strong> · {module.version}<br/>{module.description}<br/><small>{tab==="install" ? (module.kind==="connect" ? "Klaar om te koppelen." : "Klaar om te installeren.") : module.kind==="connect" ? "Gekoppeld." : "Geïnstalleerd en gekoppeld."}</small></span></label>)}</fieldset> : <p role="status">{info.empty}</p>}
      {visible.length>0 && <div className="wizard-actions"><button disabled={!selected} onClick={()=>setChosen(selected)}>Volgende</button></div>}
    </>}
  </section>;
}

/** Termix install (Docker or LXC) and, on the edit tab, check-and-repair of an existing installation. */
function TermixFlow({csrfToken,repair,onBack}:{csrfToken:string;repair:boolean;onBack:()=>void}) {
  const [step,setStep]=useState(repair ? 4 : 2);
  const [selection,setSelection]=useState<InstallSelection>({module:"termix",method:"docker",target:"local"});
  const [plan,setPlan]=useState<InstallPlan|null>(null);
  const {job,setJob,error:jobError}=useJob(csrfToken);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const run=async(action:()=>Promise<void>)=>{setBusy(true);setError("");try{await action();}catch(failure){setError(failure instanceof Error ? failure.message : "Niet beschikbaar.");}finally{setBusy(false);}};
  const review=()=>run(async()=>{setPlan(await installationRequest<InstallPlan>("/plan",csrfToken,selection));setStep(4);});
  useEffect(()=>{ if(repair) void review(); },[]); // eslint-disable-line react-hooks/exhaustive-deps
  const steps=repair ? ["Controleren","Herstellen"] : ["Docker of LXC","Bestemming","Controleren","Installeren"];
  const offset=repair ? 4 : 2;
  return <>
    <ol className="wizard-progress" aria-label="Stappen">{steps.map((label,index)=><li key={label} aria-current={step===index+offset ? "step" : undefined}>{index+1}. {label}</li>)}</ol>
    {(error || jobError) && <p role="alert">{error || jobError}</p>}
    {repair && step===4 && <p>Termix heeft geen eigen instellingen in ControlDeck. Bewerken controleert de installatie en herstelt de koppeling met je ControlDeck-login; gegevens blijven behouden.</p>}
    {step===2 && <fieldset><legend>Hoe wil je de module installeren?</legend><label className="wizard-choice"><input type="radio" name="method" checked={selection.method==="docker"} onChange={()=>setSelection({...selection,method:"docker",target:"local"})}/><span><strong>Docker</strong><br/>Een aparte container op de ControlDeck-host.</span></label><label className="wizard-choice"><input type="radio" name="method" checked={selection.method==="lxc"} onChange={()=>setSelection({...selection,method:"lxc",target:"proxmox"})}/><span><strong>Proxmox LXC</strong><br/>Automatisch een nieuwe container aanmaken via Proxmox VE Helper-Scripts.</span></label></fieldset>}
    {step===3 && <fieldset><legend>Bestemming en instellingen</legend><label>Bestemming<select value={selection.target} onChange={()=>{}}><option value={selection.target}>{selection.method==="docker" ? "Deze ControlDeck-host" : "Proxmox"}</option></select></label><p>{selection.method==="docker" ? "Termix krijgt maximaal 1 CPU en 512 MB geheugen, met een apart opslagvolume." : "Het Helper-Script gebruikt standaard 4 CPU’s, 4096 MB geheugen en 10 GB schijf, onder meer voor het bouwen van Termix."}</p><p>De module gebruikt je ControlDeck-login en wordt geopend onder Terminal.</p>{selection.method==="lxc" && <p role="status">De Proxmox-route voor LXC is nog niet beschikbaar. De volgende stap toont wat er ontbreekt.</p>}</fieldset>}
    {step===4 && plan && <section><h4>{repair ? "Controleer de installatie" : "Controleer je installatie"}</h4><dl><dt>Module</dt><dd>Termix</dd><dt>Methode</dt><dd>{plan.method==="docker" ? "Docker" : "Proxmox LXC · Helper-Scripts"}</dd><dt>Bestemming</dt><dd>{plan.target==="local" ? "Deze ControlDeck-host" : "Proxmox"}</dd>{plan.resources && <><dt>Geheugen</dt><dd>{plan.resources.memoryMb} MB</dd></>}</dl>{plan.alreadyInstalled && <p>Termix draait al. We controleren de installatie en herstellen de koppeling; bestaande gegevens blijven behouden.</p>}<ol>{plan.steps.map(item=><li key={item}>{item}</li>)}</ol>{plan.blockers.map(reason=><p role="alert" key={reason}>{reason}</p>)}</section>}
    {step===4 && !plan && busy && <p role="status">Installatie controleren…</p>}
    {step===5 && job && <section aria-live="polite"><h4>{job.status==="succeeded" ? "Module gereed" : job.status==="failed" ? "Niet afgerond" : "Wordt uitgevoerd"}</h4><p>{job.message ?? "De installatieservice start binnenkort."}</p>{job.status==="succeeded" && <a className="provider-open" href="#terminal">Open Terminal →</a>}{job.status==="failed" && <button onClick={()=>{setStep(4);setJob(null);}}>Terug naar controle</button>}</section>}
    <div className="wizard-actions">
      {step<5 && <button disabled={busy} onClick={()=>step===offset ? onBack() : setStep(step-1)}>Vorige</button>}
      {step<3 && <button onClick={()=>setStep(step+1)}>Volgende</button>}
      {step===3 && <button disabled={busy} onClick={()=>void review()}>{busy ? "Controleren…" : "Installatie controleren"}</button>}
      {step===4 && <button disabled={busy || !plan?.canInstall} onClick={()=>void run(async()=>{setJob(await installationRequest<Job>("/jobs",csrfToken,selection));setStep(5);})}>{busy ? "Klaarzetten…" : plan?.alreadyInstalled ? "Controleren en herstellen" : "Module installeren"}</button>}
      {step===5 && job && !["queued","running"].includes(job.status) && <button onClick={onBack}>Terug naar modulebeheer</button>}
    </div>
  </>;
}
