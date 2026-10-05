import icons from './service-icons.json' with {type:'json'};
const available=new Set<string>(icons);
const aliases:Record<string,string>={'seerr':'jellyseerr','proxmox backup server':'proxmox','proxmenux':'proxmox','technitium dns':'technitium','nginx proxy manager':'nginx-proxy-manager','open webui':'open-webui','home assistant':'home-assistant','uptime kuma':'uptime-kuma','speedtest tracker':'speedtest-tracker'};
/** Resolve to bundled files only: bookmark destinations are never sent to an icon service. */
export function bookmarkIcon(name:string,url:string,explicit?:string):string|null {
  if(typeof name!=='string'||typeof url!=='string')return null;
  let host:string;
  try{const parsed=new URL(url);if(!['http:','https:'].includes(parsed.protocol)||parsed.username||parsed.password)return null;host=parsed.hostname;}catch{return null;}
  const given=explicit?.replace(/\.png$/,'');
  if(given&&available.has(given))return `/service-icons/${given}.png`;
  const title=name.toLowerCase();
  const alias=Object.keys(aliases).find(key=>title.includes(key));
  const brand=alias?aliases[alias]:icons.find(key=>new RegExp(`(^|[^a-z0-9])${key}([^a-z0-9]|$)`).test(title)||host.split('.').includes(key));
  return brand?`/service-icons/${brand}.png`:null;
}
