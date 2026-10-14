/** Credentials and account selection stay behind the authenticated server endpoint. */
export async function requestAppLaunch(moduleId:string,csrfToken:string):Promise<string> {
  if(!["kasm","nextcloud"].includes(moduleId)) throw new Error("Onbekende aanmeldmodule.");
  const response=await fetch(`/api/app-launches/${moduleId}`,{method:"POST",cache:"no-store",headers:{"Content-Type":"application/json","X-CSRF-Token":csrfToken},body:"{}"});
  const result=await response.json().catch(()=>null);
  if(!response.ok||typeof result?.url!=="string")throw new Error(typeof result?.error==="string"?result.error:"Aanmelden is niet beschikbaar.");
  const url=new URL(result.url);
  if(url.protocol!=="https:"||url.username||url.password)throw new Error("Ongeldige aanmeldroute.");
  return result.url;
}
