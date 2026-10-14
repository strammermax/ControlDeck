import * as linkwarden from "./linkwarden";
/** Register module-specific UI here; the dashboard only mounts the public contract. */
import * as kasm from "./kasm";
import * as nextcloud from "./nextcloud";
const components = {linkwarden,kasm,nextcloud};
export function moduleComponents(id:string) {
  return Object.hasOwn(components,id) ? components[id as keyof typeof components] : null;
}
