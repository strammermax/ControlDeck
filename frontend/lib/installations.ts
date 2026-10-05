export type InstallSelection = {module: string; method: "docker" | "lxc"; target: "local" | "proxmox"};
export type InstallPlan = InstallSelection & {canInstall: boolean; blockers: string[]; alreadyInstalled: boolean; resources: {cpu:number;memoryMb:number};steps:string[];preservesData:boolean};
export async function installationRequest<T>(path: string, csrfToken: string, body?: InstallSelection): Promise<T> {
  const response=await fetch(`/api/installations${path}`,{cache:"no-store",method:body ? "POST" : "GET",headers:body ? {"Content-Type":"application/json","X-CSRF-Token":csrfToken} : undefined,body:body ? JSON.stringify(body):undefined});
  const data=await response.json();
  if (!data || typeof data!=="object" || Array.isArray(data)) throw new Error("Ongeldig antwoord van de installatieservice.");
  if (!response.ok) throw new Error(typeof data.error==="string" ? data.error : "Installatie niet beschikbaar.");
  return data;
}
