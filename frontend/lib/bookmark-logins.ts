export type BookmarkLogin={linkId:number;method:'sso'|'kasm'};

/** Only the bookmark ID crosses the launch boundary; never browser-selected accounts. */
export async function requestBookmarkLogin(linkId:number,csrfToken:string,bookmarkUrl:string):Promise<string> {
  if(!Number.isSafeInteger(linkId)||linkId<=0)throw new Error('Ongeldige bookmark.');
  const response=await fetch(`/api/bookmark-logins/${linkId}/launch`,{method:'POST',cache:'no-store',headers:{'Content-Type':'application/json','X-CSRF-Token':csrfToken},body:'{}'});
  const result=await response.json().catch(()=>null);
  if(!response.ok||typeof result?.url!=='string')throw new Error(typeof result?.error==='string'?result.error:'Aanmelden is niet beschikbaar.');
  const target=new URL(result.url),expected=new URL(bookmarkUrl);
  if(target.protocol!=='https:'||target.username||target.password||target.origin!==expected.origin)throw new Error('Ongeldige aanmeldroute.');
  return target.href;
}
