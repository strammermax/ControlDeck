import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {transform,loadBindings} from 'next/dist/build/swc/index.js';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {validateNetworkInventory,validateNetworkMonitor,networkSelection,networkTotals,networkSpeed,latencySummary} from '../lib/proxmox-network.ts';
const nic={node:'pve-amd',name:'nic0',kind:'physical',status:'up',addresses:['192.0.2.1'],mac:null,duplex:'full',bytes_recv:1000,bytes_sent:250,packets_recv:10,packets_sent:5,errors_in:0,errors_out:0,drops_in:0,drops_out:0,rx_Bps:100,tx_Bps:20,speed:2500,max_speed:2500,mtu:1500,used_by_bridges:['vmbr0'],bond_slaves:[],bridge_members:[],bridge_owner:'vmbr0',bond_master:null,bond_active_slave:null,bridge_physical_interface:null,bond_mode:null,vmid:null,vm_name:null,vm_type:null};
const bridge={...nic,name:'vmbr0',kind:'bridge'};
const node={name:'pve-amd',networkAvailable:true,stale:false,interfaces:[nic,bridge],latency:{current:.7,avg:.8,min:.5,max:1,history:[{time:1,value:.5},{time:2,value:.7}]},dns:['192.0.2.53'],domain:'test'};
const data=()=>validateNetworkInventory({network:{nodes:[{name:'pve-amd',online:true},{name:'pve-nas',online:true}]},updatedAt:1000,stale:false});
test('network normal: canonical selection and physical-only cluster counters',()=>{
 const monitor=validateNetworkMonitor({nodes:[node,{...node,name:'pve-nas',interfaces:[{...nic,node:'pve-nas'}]}]});
 const view=networkSelection(data(),monitor);assert.equal(view.incomplete,false);
 const totals=networkTotals(view.interfaces);assert.equal(totals.received,2000);assert.equal(totals.sent,500);assert.equal(totals.rx,200);
 assert.equal(totals.bridge.total,1);assert.equal(totals.physical.total,2);
 assert.equal(networkSelection(data(),monitor,'pve-amd').interfaces.length,2);
 assert.equal(networkSpeed(2500),'2.5 Gbps');assert.equal(latencySummary(monitor).current,.7);
});
test('network boundary: unknown differs from zero; stale/missing and retired nodes cannot claim completeness',()=>{
 const rows=[{...nic,rx_Bps:null,bytes_recv:null}];assert.equal(networkTotals(rows).rx,null);assert.equal(networkTotals(rows).received,null);
 assert.equal(networkTotals([{...nic,rx_Bps:0}]).rx,0);assert.equal(networkTotals([]).received,null);
 const view=networkSelection(data(),[node,{...node,name:'old-node',interfaces:[{...nic,node:'old-node'}]}]);
 assert.equal(view.interfaces.length,2);assert.equal(view.incomplete,true);
 assert.equal(networkSelection(data(),[{...node,stale:true}],'pve-amd').incomplete,true);
 assert.equal(latencySummary([{...node,stale:true}]).current,null);assert.equal(latencySummary([]).complete,false);
 assert.equal(latencySummary([{...node,latency:{...node.latency,current:0}}]).current,0);
});
test('network rejection: malformed schema, duplicates, wrong node, nonfinite/negative amounts',()=>{
 for(const v of [null,{}, {network:{nodes:[{name:'bad/host',online:true}]},updatedAt:1,stale:false}])assert.throws(()=>validateNetworkInventory(v));
 for(const v of [null,{}, {nodes:[node,node]},{nodes:[{...node,interfaces:[nic,nic]}]},{nodes:[{...node,interfaces:[{...nic,node:'pve-nas'}]}]},{nodes:[{...node,interfaces:[{...nic,rx_Bps:Infinity}]}]},{nodes:[{...node,interfaces:[{...nic,bytes_recv:-1}]}]},{nodes:[{...node,latency:{...node.latency,history:[{time:1,value:NaN}]}}]},{nodes:[{...node,loading:'true'}]}])assert.throws(()=>validateNetworkMonitor(v));
});
await loadBindings();
async function compile(path,replacements={}){
 let {code}=await transform(readFileSync(new URL(path,import.meta.url),'utf8'),{filename:path,jsc:{parser:{syntax:'typescript',tsx:true},target:'es2022',transform:{react:{runtime:'automatic'}}},module:{type:'es6'}});
 for(const name of ['react','react/jsx-runtime'])code=code.replaceAll(`from "${name}"`,`from ${JSON.stringify(import.meta.resolve(name))}`);
 for(const [name,url] of Object.entries(replacements))code=code.replaceAll(`from "${name}"`,`from ${JSON.stringify(url)}`);
 return 'data:text/javascript;base64,'+Buffer.from(code).toString('base64');
}
const libURL=new URL('../lib/proxmox-network.ts',import.meta.url).href;
const guestURL=new URL('../lib/proxmox-guests.ts',import.meta.url).href;
const shared=await compile('../modules/proxmox/guest-cards.tsx',{'../../lib/proxmox-guests':guestURL,'./pve-tag-color':new URL('../modules/proxmox/pve-tag-color.ts',import.meta.url).href});
const cardsURL=await compile('../modules/proxmox/network-cards.tsx',{'./guest-cards':shared,'../../lib/proxmox-guests':guestURL,'../../lib/proxmox-network':libURL});
const ui=await import(cardsURL);
const flowURL=await compile('../modules/proxmox/network-flow.tsx');
const flowDataURL=await compile('../lib/proxmox-network-flow.ts',{'./proxmox-network':libURL});
const clusterURL=await compile('../modules/proxmox/cluster-network-flow.tsx',{'../../lib/proxmox-network-flow':flowDataURL,'./network-flow':flowURL,'./guest-cards':shared});
const flowUI=await import(clusterURL);
const page=await import(await compile('../components/proxmox-network.tsx',{'../lib/proxmox-network':libURL,'../modules/proxmox/network-cards':cardsURL,'../modules/proxmox/cluster-network-flow':clusterURL,'./proxmox-guests.css':'data:text/javascript,export default {}','./proxmox-network.css':'data:text/javascript,export default {}'}).then(url=>{let code=Buffer.from(url.split(',')[1],'base64').toString();code=code.replace(/import "\.\/proxmox-(?:guests|network)\.css";?/g,'');return 'data:text/javascript;base64,'+Buffer.from(code).toString('base64');}));
const render=(component,props)=>renderToStaticMarkup(React.createElement(component,props));
test('actual ProxMenux network cards: overview and physical card with relations, speed and escaped guest name',()=>{
 const html=render(ui.NetworkOverview,{rows:[nic,bridge],nodes:[node]});
 for(const text of ['Network Traffic','Active Interfaces','Network Status','Gateway Latency','2','0.7','no errors / drops'])assert.ok(html.includes(text),text);
 const card=render(ui.InterfaceCard,{item:{...nic,vm_name:'<script>bad</script>'}});
 for(const text of ['2.5 Gbps','192.0.2.1','vmbr0','pve-amd','&lt;script&gt;bad'])assert.ok(card.includes(text),text);
 assert.ok(!card.includes('<script>'));assert.ok(card.includes('Received'));
 assert.ok(render(flowUI.ClusterNetworkFlow,{nodes:[node]}).includes('Network Flow'));
});
test('actual network boundary/failure UI: missing and failed measurements never appear healthy',()=>{
 const html=render(ui.NetworkOverview,{rows:[],nodes:[{name:'pve-amd',error:'Unavailable'}],incomplete:true});
 assert.ok(html.includes('Onvolledig'));assert.ok(!html.includes('no errors / drops'));assert.ok(html.includes('—'));assert.ok(!/NaN|Infinity/.test(html));
 assert.ok(render(ui.LatencySparkline,{node:{...node,latency:{...node.latency,history:[]}}}).includes('—'));
 const view=render(page.NetworkInventoryView,{data:data(),monitor:[node]});
 for(const text of ['Cluster','pve-amd','pve-nas','aria-pressed="true"','Zoek netwerkinterface','Niet alle netwerkmetingen'])assert.ok(view.includes(text),text);
 assert.ok(render(page.NetworkInventoryView,{data:data(),monitor:[]}).includes('Nog geen netwerkgegevens'));
});
