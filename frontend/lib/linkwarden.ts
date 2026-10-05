export type Bookmark = {id:number;url:string;name:string;description:string;collection:string;tags:string[]};
export type BookmarkPage = {links:Bookmark[];nextCursor:number|null};
export async function linkwardenRequest<T>(path:string, csrfToken:string, method='GET', body?:unknown):Promise<T> {
  const response=await fetch(`/api/linkwarden${path}`,{cache:'no-store',method,
    headers:method==='GET' ? undefined : {'Content-Type':'application/json','X-CSRF-Token':csrfToken},
    body:body===undefined ? undefined : JSON.stringify(body)});
  const data=await response.json().catch(()=>null);
  if (!response.ok || !data || typeof data!=='object' || Array.isArray(data)) throw new Error(typeof data?.error==='string' ? data.error : 'Linkwarden is niet beschikbaar.');
  return data;
}
