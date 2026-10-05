export type Bookmark = {id:number;url:string;name:string;description:string;collection:string;tags:string[]};
export type BookmarkPage = {links:Bookmark[];nextCursor:number|null};
export const LINKWARDEN_LXC_COMMAND = 'bash -c "$(curl -fsSL https://raw.githubusercontent.com/community-scripts/ProxmoxVE/main/ct/linkwarden.sh)"';
export function guidedLxcSteps(node:string):string[] {
  if (!/^[A-Za-z0-9][A-Za-z0-9.-]{0,62}$/.test(node)) throw new Error('Kies een geldige Proxmox-node.');
  return [`Open in Proxmox de Shell van node ${node}.`,
    'Voer het onderstaande Helper-Script uit als root op deze Proxmox-host.',
    'Kies in het Helper-Script de container-ID, opslag, netwerk en benodigde resources.',
    'Wacht totdat de installatie gereed is en noteer het Linkwarden-adres (standaard poort 3000).',
    'Stel de gewenste HTTPS-route in. Ga daarna verder om het adres en je persoonlijke API-token te koppelen.'];
}
export async function linkwardenRequest<T>(path:string, csrfToken:string, method='GET', body?:unknown):Promise<T> {
  const response=await fetch(`/api/linkwarden${path}`,{cache:'no-store',method,
    headers:method==='GET' ? undefined : {'Content-Type':'application/json','X-CSRF-Token':csrfToken},
    body:body===undefined ? undefined : JSON.stringify(body)});
  const data=await response.json().catch(()=>null);
  if (!response.ok || !data || typeof data!=='object' || Array.isArray(data)) throw new Error(typeof data?.error==='string' ? data.error : 'Linkwarden is niet beschikbaar.');
  return data;
}
