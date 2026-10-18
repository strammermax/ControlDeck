import type {NetworkNode} from "../../lib/proxmox-network";
import {networkFlowData} from "../../lib/proxmox-network-flow";
import {NetworkFlow} from "./network-flow";
import {GuestIcon} from "./guest-cards";
export function ClusterNetworkFlow({nodes}:{nodes:NetworkNode[]}) {
 return <section className="pm-card pm-cluster-flow"><header className="pm-list-head"><h3><GuestIcon kind="network"/>Network Flow</h3><span className="pm-badge">{nodes.length} nodes</span></header><div className="pm-list-content">{nodes.map(node=>{
  const flow=networkFlowData(node);
  return <div key={node.name}>{node.interfaces?.length?<NetworkFlow data={flow.data}/>:<p className="pm-muted">{node.name}: netwerkgegevens niet beschikbaar.</p>}{(node.stale||node.error)&&<p role="status" className="pm-muted">{node.name}: deze topologie is mogelijk verouderd.</p>}{flow.unmapped.length>0&&<p className="pm-muted">{node.name}: {flow.unmapped.length} interface(s) zonder aangetoonde bridgekoppeling staan bij ‘Onbekende bridge’.</p>}{flow.truncated&&<p role="status" className="pm-muted">{node.name}: het diagram is begrensd; de interfacelijst bevat alle ontvangen gegevens.</p>}</div>;
 })}<p className="pm-footnote">Origineel ProxMenux-diagram per host, samen in één clusteroverzicht. Lijnen volgen de gemelde NIC-, bond-, bridge- en gastkoppelingen. Switches en kabelverbindingen tussen hosts worden niet verondersteld. Snelheid onbekend: —; gemeten activiteit geeft RX/TX-animatie. Bij verminderde beweging staan animaties uit.</p></div></section>;
}
