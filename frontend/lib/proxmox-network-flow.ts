import type {NetworkInterface,NetworkNode} from "./proxmox-network";
import {networkSpeed} from "./proxmox-network";
import type {NetworkFlowData} from "../modules/proxmox/network-flow";
/** Node-local identities stay local: vmbr0 on two hosts is never the same bridge. */
export function networkFlowData(node:NetworkNode) {
 const rows=node.interfaces??[],physical=rows.filter(i=>i.kind==="physical"),bonds=rows.filter(i=>i.kind==="bond"),bridges=rows.filter(i=>i.kind==="bridge");
 const guests=rows.filter(i=>i.kind==="virtual").slice(0,512),unmapped:string[]=[];
 const rates=(i:NetworkInterface)=>({rx:node.stale||node.error?0:(i.rx_Bps??0)/1024**2,tx:node.stale||node.error?0:(i.tx_Bps??0)/1024**2,rateKnown:!node.stale&&!node.error&&i.rx_Bps!==null&&i.tx_Bps!==null});
 const consumers:NetworkFlowData["consumers"]=guests.map(i=>{
  const owner=bridges.find(b=>b.name===i.bridge_owner)||bridges.find(b=>b.bridge_members.includes(i.name)||i.bridge_owner!==null&&b.bridge_members.includes(i.bridge_owner));
  if(!owner)unmapped.push(i.name);
  return {id:i.name,label:i.vm_name??i.name,kind:i.vm_type==="vm"?"vm":"lxc",bridge:owner?.name??"Onbekende bridge",...rates(i),offline:i.vm_status==="stopped"};
 });
 const running=consumers.filter(c=>!c.offline);
 const data:NetworkFlowData={hostLabel:node.name,nics:physical.slice(0,64).map(i=>{
  const bond=bonds.find(b=>b.name===i.bond_master||b.name===i.bridge_owner||b.bond_slaves.includes(i.name));
  const role=i.bond_role??(bond?.bond_mode==="active-backup"&&bond.bond_active_slave?bond.bond_active_slave===i.name?"active":"standby":undefined);
  return {id:i.name,link:networkSpeed(i.speed),...rates(i),status:i.bond_link==="down"?"down":i.status==="up"?"up":i.status==="down"?"down":undefined,bond:bond?.name,role};
 }),bonds:bonds.slice(0,64).map(i=>({id:i.name,mode:i.bond_mode??undefined,...rates(i),status:i.status==="up"?"up":i.status==="down"?"down":undefined})),bridges:bridges.slice(0,127).map(i=>({id:i.name,parent:i.bridge_physical_interface??undefined})),consumers:[{id:"host",label:node.name,kind:"host",bridge:bridges[0]?.name??"",rx:running.reduce((a,c)=>a+c.rx,0),tx:running.reduce((a,c)=>a+c.tx,0),rateKnown:running.length>0&&running.every(c=>c.rateKnown)},...consumers]};
 if(unmapped.length)data.bridges.push({id:"Onbekende bridge"});
 return {data,unmapped,truncated:guests.length!==rows.filter(i=>i.kind==="virtual").length||physical.length>64||bonds.length>64||bridges.length>127};
}
