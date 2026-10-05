"use client";
import {useEffect,useState} from 'react';
import {linkwardenRequest} from '../lib/linkwarden';
import {installationRequest,type InstallPlan,type InstallSelection} from '../lib/installations';
import {useJob,type Job} from './use-job';

export function LinkwardenConnect({csrfToken,onBack,remove=false}:{csrfToken:string;onBack:()=>void;remove?:boolean}) {
  const [method,setMethod]=useState('existing');
  const [url,setUrl]=useState('https://linkwarden.example.com');
  const [token,setToken]=useState('');
  const [plan,setPlan]=useState<InstallPlan|null>(null);
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  const {job,setJob,error:jobError}=useJob(csrfToken);
  useEffect(()=>{linkwardenRequest<{connected:boolean;url?:string}>('/connection',csrfToken).then(value=>{if(value.url)setUrl(value.url);}).catch(failure=>setError(failure.message));},[csrfToken]);
  const selection:InstallSelection={module:'linkwarden',method:method==='lxc'?'lxc':'docker',target:method==='lxc'?'proxmox':'local'};
  return <section><h3>{remove?'Linkwarden ontkoppelen':'Linkwarden voor Bookmarks'}</h3>{(error||jobError)&&<p role="alert">{error||jobError}</p>}
    {remove?<><p>Dit verwijdert alleen de verbinding in ControlDeck. De Linkwarden-server, bookmarks en persoonlijke tokens blijven bestaan.</p><button onClick={async()=>{try{await linkwardenRequest('/connection',csrfToken,'DELETE');onBack();}catch(failure){setError(failure instanceof Error?failure.message:'Niet beschikbaar.');}}}>Verbinding verwijderen</button></>:<>
    <fieldset><legend>Hoe wil je Linkwarden gebruiken?</legend>{[['existing','Bestaande Linkwarden koppelen'],['docker','Nieuwe Docker-installatie'],['lxc','Nieuwe Proxmox LXC']].map(([id,label])=><label className="wizard-choice" key={id}><input type="radio" checked={method===id} onChange={()=>{setMethod(id);setPlan(null);setJob(null);}}/><strong>{label}</strong></label>)}</fieldset>
    {method==='existing'?<form className="bookmark-form" onSubmit={async event=>{event.preventDefault();setBusy(true);setError('');try{await linkwardenRequest('/connection',csrfToken,'PUT',{url});if(token){await linkwardenRequest('/token',csrfToken,'PUT',{token});setToken('');}onBack();}catch(failure){setError(failure instanceof Error?failure.message:'Niet beschikbaar.');}finally{setBusy(false);}}}><label>Linkwarden-adres<input type="url" required value={url} onChange={event=>setUrl(event.target.value)}/></label><label>Mijn persoonlijke API-token (optioneel)<input type="password" autoComplete="off" value={token} onChange={event=>setToken(event.target.value)} minLength={20} maxLength={4096}/></label><p>Hier kun je meteen je eigen token koppelen. Later kan dit ook via Bookmarks → Mijn koppeling.</p><p>Iedere gebruiker koppelt daarna een eigen API-token in Bookmarks. Google-login en het ControlDeck-thema blijven actief.</p><button disabled={busy} type="submit">Controleren en koppelen</button></form>:<>
    <p>{method==='docker'?'Docker Compose installeert Linkwarden en PostgreSQL met blijvende opslag. Het lichte profiel schakelt browserarchivering en MeiliSearch uit.':'Een nieuwe LXC via het officiële Proxmox VE Helper-Script. De uitvoerende Proxmox-hostverbinding moet eerst worden aangesloten.'}</p>
    <button disabled={busy} onClick={async()=>{setBusy(true);setError('');try{setPlan(await installationRequest<InstallPlan>('/plan',csrfToken,selection));}catch(failure){setError(failure instanceof Error?failure.message:'Niet beschikbaar.');}finally{setBusy(false);}}}>Installatie controleren</button>
    {plan&&<><ol>{plan.steps.map(step=><li key={step}>{step}</li>)}</ol>{plan.blockers.map(reason=><p role="alert" key={reason}>{reason}</p>)}<button disabled={busy||!plan.canInstall} onClick={async()=>{try{setJob(await installationRequest<Job>('/jobs',csrfToken,selection));}catch(failure){setError(failure instanceof Error?failure.message:'Niet beschikbaar.');}}}>Linkwarden installeren</button></>}
    {job&&<p role="status">{job.message??'Wachten op de installatieservice…'}</p>}
    </>}
    <p>De Linkwarden-browserextensie gebruikt dezelfde server. Persoonlijke en gedeelde collecties blijven door Linkwarden beheerd.</p>
    </>}
    <div className="wizard-actions"><button onClick={onBack}>Terug naar modulebeheer</button>{job?.status==='succeeded'&&<a href="#bookmarks">Open Bookmarks →</a>}</div>
  </section>;
}
