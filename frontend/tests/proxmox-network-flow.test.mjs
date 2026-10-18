import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {transform,loadBindings} from 'next/dist/build/swc/index.js';
await loadBindings();
async function compile(path,replacements={}){
 let {code}=await transform(readFileSync(new URL(path,import.meta.url),'utf8'),{filename:path,jsc:{parser:{syntax:'typescript',tsx:true},target:'es2022',transform:{react:{runtime:'automatic'}}},module:{type:'es6'}});
 for(const name of ['react','react/jsx-runtime'])code=code.replaceAll(`from "${name}"`,`from ${JSON.stringify(import.meta.resolve(name))}`);
 for(const [name,url] of Object.entries(replacements))code=code.replaceAll(`from "${name}"`,`from ${JSON.stringify(url)}`);
 return 'data:text/javascript;base64,'+Buffer.from(code).toString('base64');
}
const flow=await import(await compile('../modules/proxmox/network-flow.tsx'));
const adapter=await import(await compile('../lib/proxmox-network-flow.ts',{'./proxmox-network':new URL('../lib/proxmox-network.ts',import.meta.url).href}));
const rates={rx:1,tx:.1,rateKnown:true};
const data=()=>({hostLabel:'pve-amd',nics:[{id:'nic0',link:'2.5 Gbps',status:'up',bond:'bond0',...rates}],bonds:[{id:'bond0',mode:'active-backup',status:'up',...rates}],bridges:[{id:'vmbr0'},{id:'idle-bridge'}],consumers:[{id:'host',label:'pve-amd',kind:'host',bridge:'vmbr0',...rates},{id:'veth1',label:'ControlDeck',kind:'lxc',bridge:'vmbr0',...rates}]});
const iface={node:'pve-amd',name:'nic0',kind:'physical',status:'up',speed:2500,rx_Bps:1024**2,tx_Bps:1024,bridge_owner:'bond0',bond_master:'bond0',used_by_bridges:['vmbr0'],bond_slaves:[],bridge_members:[],bond_mode:null,bond_active_slave:null,vm_name:null,vm_type:null};
test('upstream Network Flow normal: actual SVG contains NIC, bond, named host, idle bridge and guest with animated RX/TX paths',()=>{
 for(const mobile of [false,true]){
  const out=flow.networkFlowLayout(data(),mobile);
  for(const text of ['nic0','bond0','pve-amd','vmbr0','idle-bridge','ControlDeck'])assert.ok(out.svg.includes(text),text);
  assert.ok(out.pulses.length>0);assert.ok(out.pulses.some(p=>p.type==='rx'));assert.ok(out.pulses.some(p=>p.type==='tx'));
  assert.ok(out.height>0);assert.ok(!/NaN|undefined|Infinity/.test(out.svg));
 }
});
test('upstream Network Flow boundary: empty, unknown rates and stopped guests never invent activity',()=>{
 const empty=flow.networkFlowLayout({nics:[],bridges:[],consumers:[],hostLabel:'Empty'});assert.ok(empty.svg.includes('Empty'));assert.equal(empty.pulses.length,0);
 const unknown=data();unknown.consumers=unknown.consumers.map(g=>({...g,rx:0,tx:0,rateKnown:false}));unknown.nics=unknown.nics.map(n=>({...n,rx:0,tx:0}));unknown.bonds=[];
 const out=flow.networkFlowLayout(unknown);assert.ok(out.svg.includes('—'));assert.equal(out.pulses.length,0);
 const stopped=data();stopped.consumers[1].offline=true;assert.ok(!flow.networkFlowLayout(stopped).svg.includes('ControlDeck'));
});
test('Network Flow rejection and SVG injection regression: upstream interpolated labels directly into innerHTML',()=>{
 const malicious=data();malicious.hostLabel='<script>host</script>';malicious.nics[0].id='nic" onload="alert(1)';malicious.nics[0].link='<image href="bad">';malicious.consumers[1].label='<script>guest</script>';
 for(const mobile of [false,true]){
  const html=flow.networkFlowLayout(malicious,mobile).svg;
  assert.ok(!html.includes('<script>'));assert.ok(!html.includes('<image'));assert.ok(!html.includes(' onload="'));
  assert.ok(html.includes('&lt;script&gt;'));assert.ok(html.includes('&quot;'));
 }
 for(const invalid of [null,{}, {...data(),nics:Array(65).fill(data().nics[0])},{...data(),consumers:[{...data().consumers[0],kind:'"><script>bad</script>'}]},{...data(),nics:[{...data().nics[0],rx:NaN}]}])assert.throws(()=>flow.networkFlowLayout(invalid));
});
test('cluster flow adapter normal: real bond/bridge membership and node-local identities',()=>{
 const bond={...iface,name:'bond0',kind:'bond',bond_mode:'active-backup',bond_active_slave:'nic0',bond_slaves:['nic0']};
 const bridge={...iface,name:'vmbr0',kind:'bridge',bridge_members:['veth1']};
 const guest={...iface,name:'veth1',kind:'virtual',bridge_owner:'vmbr0',vm_name:'ControlDeck',vm_type:'lxc',vm_status:'running'};
 const first=adapter.networkFlowData({name:'pve-amd',interfaces:[iface,bond,bridge,guest]});
 assert.equal(first.data.nics[0].bond,'bond0');assert.equal(first.data.nics[0].role,'active');assert.equal(first.data.consumers[1].bridge,'vmbr0');assert.deepEqual(first.unmapped,[]);
 const second=adapter.networkFlowData({name:'pve-nas',interfaces:[{...bridge,node:'pve-nas'}]});assert.equal(second.data.hostLabel,'pve-nas');assert.equal(second.data.consumers.length,1);
 assert.equal(first.data.consumers[1].label,'ControlDeck');
});
test('cluster flow boundary/failure: unknown bridge never defaults to first, stale data has no pulses, oversized diagrams report truncation',()=>{
 const bridge={...iface,name:'vmbr0',kind:'bridge',bridge_members:[]};
 const guest={...iface,name:'veth1',kind:'virtual',bridge_owner:'missing',vm_name:'Unknown guest',vm_type:'lxc',rx_Bps:null,tx_Bps:null};
 const missing=adapter.networkFlowData({name:'pve-amd',interfaces:[iface,bridge,guest]});
 assert.equal(missing.data.consumers[1].bridge,'Onbekende bridge');assert.deepEqual(missing.unmapped,['veth1']);assert.equal(missing.data.consumers[1].rateKnown,false);
 const stale=adapter.networkFlowData({name:'pve-amd',stale:true,interfaces:[iface,bridge,{...guest,bridge_owner:'vmbr0',rx_Bps:1024**2,tx_Bps:1024**2}]});
 assert.equal(flow.networkFlowLayout(stale.data).pulses.length,0);
 assert.equal(adapter.networkFlowData({name:'pve-amd',interfaces:Array.from({length:513},(_,i)=>({...guest,name:`veth${i}`}))}).truncated,true);
});
