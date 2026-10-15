import * as linkwarden from "./linkwarden";
/** Register module-specific UI here; the dashboard only mounts the public contract. */
import * as kasm from "./kasm";
import * as nextcloud from "./nextcloud";
import * as proxmox from "./proxmox";
import * as system from "./system";
import {serviceModule} from "./service";
const components = {linkwarden,kasm,nextcloud,proxmox,system,downloads:serviceModule("downloads"),"media-widget":serviceModule("media-widget"),tdarr:serviceModule("tdarr"),"homeassistant-dashboard":serviceModule("homeassistant-dashboard"),calendar:serviceModule("calendar"),statistics:serviceModule("statistics")};
export function moduleComponents(id:string) {
  return Object.hasOwn(components,id) ? components[id as keyof typeof components] : null;
}
