"use client";
import {useState} from 'react';
import {Modal} from './modal';
import type {Bookmark} from '../lib/linkwarden';

export function BookmarkLoginSettings({link,csrfToken,available,configured,onClose,onSaved}:{link:Bookmark;csrfToken:string;available:boolean;configured:boolean;onClose:()=>void;onSaved:()=>void}) {
  const [method,setMethod]=useState('sso'),[loginUrl,setLoginUrl]=useState('');
  const [apiKey,setApiKey]=useState(''),[apiSecret,setApiSecret]=useState(''),[userId,setUserId]=useState('');
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  async function save(remove=false) {
    setBusy(true);setError('');
    try {
      const response=await fetch(`/api/bookmark-logins/${link.id}`,{method:remove?'DELETE':'PUT',headers:{'Content-Type':'application/json','X-CSRF-Token':csrfToken},body:remove?undefined:JSON.stringify(method==='sso'?{method,loginUrl}:{method,apiKey,apiSecret,userId})});
      const result=await response.json();if(!response.ok)throw new Error(result.error||'Opslaan is mislukt.');
      setApiKey('');setApiSecret('');onSaved();onClose();
    }catch(failure){setError(failure instanceof Error?failure.message:'Opslaan is mislukt.');}finally{setBusy(false);}
  }
  return <Modal open title={`Mijn aanmelding: ${link.name}`} onClose={onClose}>
    <form className="bookmark-form in-modal" onSubmit={event=>{event.preventDefault();void save();}}>
      <p>Deze aanmelding geldt alleen voor jouw ControlDeck-account. Gegevens worden in Keyvault bewaard en niet teruggetoond.</p>
      {!available?<p role="alert">Keyvault is nog niet gekoppeld. Laat de beheerder eerst de verbinding instellen.</p>:<>
        {configured&&<p>Er is al een aanmelding ingesteld. Vul opnieuw in om die te vervangen, of verwijder de koppeling.</p>}
        <label>Aanmeldmethode<select value={method} onChange={event=>setMethod(event.target.value)}><option value="sso">Bestaande Google/SSO-aanmeldroute</option><option value="kasm">Kasm API-aanmelding</option></select></label>
        {method==='sso'?<><label>SSO-aanmeldadres<input type="url" required value={loginUrl} onChange={event=>setLoginUrl(event.target.value)} maxLength={2048}/></label><p>Gebruik de vaste HTTPS-aanmeldroute van deze app op hetzelfde adres. Dit vereist dat SSO al in de app is ingesteld.</p></>:<>
          <label>API-sleutel<input type="password" required autoComplete="new-password" maxLength={4096} value={apiKey} onChange={event=>setApiKey(event.target.value)}/></label>
          <label>API-geheim<input type="password" required autoComplete="new-password" maxLength={4096} value={apiSecret} onChange={event=>setApiSecret(event.target.value)}/></label>
          <label>Jouw Kasm-gebruiker-ID<input required maxLength={36} value={userId} onChange={event=>setUserId(event.target.value)}/></label>
          <p>De Kasm API moet via het HTTPS-adres van deze bookmark bereikbaar zijn. De sleutel moet toestemming voor get_login hebben.</p>
        </>}
        <p>Een gewone gebruikersnaam/wachtwoord of API-sleutel van een andere app geeft niet automatisch toegang tot diens webinterface.</p>
        <div className="form-actions"><button disabled={busy}>Bewaren in Keyvault</button>{configured&&<button type="button" disabled={busy} onClick={()=>void save(true)}>Aanmelding verwijderen</button>}</div>
      </>}
      <button type="button" disabled={busy} onClick={onClose}>Sluiten</button>
      {error&&<p role="alert" className="config-error">{error}</p>}
    </form>
  </Modal>;
}
