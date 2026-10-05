export type InstallSelection = {module: string; method: "docker" | "lxc"; target: "local" | "proxmox"; action?: "install" | "uninstall"; keepData?: boolean};
export type InstallPlan = InstallSelection & {canInstall: boolean; blockers: string[]; alreadyInstalled: boolean; resources: {cpu:number;memoryMb:number} | null;steps:string[];preservesData:boolean};
export type CatalogModule = {id: string; name: string; kind: "install" | "connect"; description: string; version: string; installed: boolean};
export type ManageTab = "install" | "edit" | "remove";
export async function installationRequest<T>(path: string, csrfToken: string, body?: InstallSelection): Promise<T> {
  const response=await fetch(`/api/installations${path}`,{cache:"no-store",method:body ? "POST" : "GET",headers:body ? {"Content-Type":"application/json","X-CSRF-Token":csrfToken} : undefined,body:body ? JSON.stringify(body):undefined});
  const data=await response.json();
  if (!data || typeof data!=="object" || Array.isArray(data)) throw new Error("Ongeldig antwoord van de installatieservice.");
  if (!response.ok) throw new Error(typeof data.error==="string" ? data.error : "Installatie niet beschikbaar.");
  return data;
}
/** Install shows only modules that are not installed; edit and remove only installed ones. Unknown state counts as not installed. */
export function modulesFor(tab: ManageTab, modules: readonly CatalogModule[]): CatalogModule[] {
  if (!Array.isArray(modules)) throw new TypeError("Modules must be a list");
  return modules.filter(module => tab === "install" ? module.installed !== true : module.installed === true);
}
