"use client";
import {useState} from "react";
import {installationRequest,type CatalogModule,type InstallPlan,type InstallSelection} from "../lib/installations";
import {useJob,type Job} from "./use-job";

type Info={effects:string[];afterwards:{text:string;command?:string}[]};
// What removal means per module; shown before anything happens.
const INFO:Record<string,Info>={
  cronjobs:{effects:["ControlDeck vergeet de hostsleutels van alle gekoppelde nodes en kan de agent niet meer gebruiken.","De SSH-sleutel blijft op de ControlDeck-host; koppel je later opnieuw, dan wordt hij hergebruikt."],afterwards:[{text:"Haal de sleutel van ControlDeck weg uit authorized_keys (gedeeld binnen het cluster, dus één keer op een node). Gebruik geen sed -i: dat vervangt de symlink naar het gedeelde clusterbestand:",command:"grep -vF 'command=\"/usr/local/sbin/controldeck-agent\"' /root/.ssh/authorized_keys > /tmp/authorized_keys.new; cat /tmp/authorized_keys.new > /root/.ssh/authorized_keys && rm /tmp/authorized_keys.new"},{text:"Optioneel per node de agent en de ControlDeck-cronjobs verwijderen:",command:"rm -f /usr/local/sbin/controldeck-agent /etc/cron.d/controldeck && rm -rf /etc/controldeck-agent /var/lib/controldeck-agent"}]},
  termix:{effects:["De Terminal-module sluit voor alle gebruikers; open terminalsessies worden verbroken.","De Termix-container en de gateway worden verwijderd. Docker en Nginx blijven staan.","Kies hieronder of de Termix-gegevens (SSH-hosts, sleutels, opnamen) bewaard blijven."],afterwards:[]},
  proxmox:{effects:["Proxmox → Overzicht toont geen widgets en taken meer.","Het opgeslagen API-token en de certificaatgegevens worden van de ControlDeck-server verwijderd."],afterwards:[{text:"Trek het token ook in Proxmox in:",command:"pveum user token remove controldeck@pve controldeck"},{text:"Optioneel de gebruiker verwijderen:",command:"pveum user delete controldeck@pve"}]},
  proxmenux:{effects:["Gezondheid, schijven en LXC-updates verdwijnen uit Proxmox → Overzicht.","De API-tokens en de cluster-CA worden van de ControlDeck-server verwijderd. ProxMenux zelf blijft op de nodes draaien."],afterwards:[{text:"Trek de tokens ook in elke monitor in: Settings → Security → API tokens."}]},
};

/** Removal wizard: consequences, explicit confirmation by typing the module name, then execution. */
export function ModuleRemove({module,csrfToken,onDone}:{module:CatalogModule;csrfToken:string;onDone:()=>void}) {
  const [step,setStep]=useState(1);
  const [keepData,setKeepData]=useState(true);
  const [plan,setPlan]=useState<InstallPlan|null>(null);
  const [typed,setTyped]=useState("");
  const [done,setDone]=useState(false);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const {job,setJob,error:jobError}=useJob(csrfToken);
  const info=INFO[module.id] ?? {effects:["De module wordt ontkoppeld."],afterwards:[]};
  const selection:InstallSelection={module:"termix",method:"docker",target:"local",action:"uninstall",keepData};
  const run=async(action:()=>Promise<void>)=>{setBusy(true);setError("");try{await action();}catch(failure){setError(failure instanceof Error ? failure.message : "Verwijderen is niet gelukt.");}finally{setBusy(false);}};
  const next=()=>run(async()=>{ if(module.id==="termix") setPlan(await installationRequest<InstallPlan>("/plan",csrfToken,selection)); setStep(2); });
  const remove=()=>run(async()=>{
    if(module.id==="termix"){ setJob(await installationRequest<Job>("/jobs",csrfToken,selection)); }
    else{
      const response=await fetch(`/api/${module.id}/connection`,{method:"DELETE",headers:{"X-CSRF-Token":csrfToken}});
      if(!response.ok) throw new Error("De koppeling kan niet worden verwijderd.");
      setDone(true);
    }
    setStep(3);
  });
  const finished=done || job?.status==="succeeded";
  return <>
    <ol className="wizard-progress" aria-label="Verwijderstappen">{["Gevolgen","Bevestigen","Verwijderen"].map((label,index)=><li key={label} aria-current={step===index+1 ? "step" : undefined}>{index+1}. {label}</li>)}</ol>
    {(error || jobError) && <p role="alert">{error || jobError}</p>}
    {step===1 && <section><h4>{module.name} verwijderen: wat gebeurt er?</h4><ul>{info.effects.map(item=><li key={item}>{item}</li>)}</ul>
      {module.id==="termix" && <fieldset><legend>Termix-gegevens</legend>
        <label className="wizard-choice"><input type="radio" name="data" checked={keepData} onChange={()=>setKeepData(true)}/><span><strong>Gegevens bewaren</strong> (aanbevolen)<br/>Het volume blijft staan; bij opnieuw installeren is alles terug.</span></label>
        <label className="wizard-choice"><input type="radio" name="data" checked={!keepData} onChange={()=>setKeepData(false)}/><span><strong>Alles verwijderen</strong><br/>Verbindingen, sleutels en opnamen worden definitief gewist.</span></label>
      </fieldset>}
    </section>}
    {step===2 && <section><h4>Bevestigen</h4>
      {plan && <><ol>{plan.steps.map(item=><li key={item}>{item}</li>)}</ol>{plan.blockers.map(reason=><p role="alert" key={reason}>{reason}</p>)}</>}
      <label>Typ <strong>{module.name}</strong> om te bevestigen<input value={typed} onChange={event=>setTyped(event.target.value)} autoComplete="off" spellCheck={false}/></label>
    </section>}
    {step===3 && <section aria-live="polite"><h4>{finished ? `${module.name} is verwijderd` : job?.status==="failed" ? "Verwijderen niet afgerond" : "Wordt verwijderd…"}</h4>
      {job?.message && <p>{job.message}</p>}
      {finished && info.afterwards.length>0 && <><p>Rond het af buiten ControlDeck:</p><ul>{info.afterwards.map(item=><li key={item.text}>{item.text}{item.command && <pre className="command">{item.command}</pre>}</li>)}</ul></>}
    </section>}
    <div className="wizard-actions">
      {step<3 && <button disabled={busy} onClick={()=>step===1 ? onDone() : setStep(1)}>Vorige</button>}
      {step===1 && <button disabled={busy} onClick={()=>void next()}>Volgende</button>}
      {step===2 && <button className="danger" disabled={busy || typed.trim()!==module.name || (plan!==null && !plan.canInstall)} onClick={()=>void remove()}>{busy ? "Verwijderen…" : `${module.name} verwijderen`}</button>}
      {step===3 && (finished || job?.status==="failed") && <button onClick={onDone}>Terug naar modulebeheer</button>}
    </div>
  </>;
}
