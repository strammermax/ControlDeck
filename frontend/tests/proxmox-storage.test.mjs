import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {transform,loadBindings} from 'next/dist/build/swc/index.js';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {storageSelection,storageMonitorSelection,storageTotals,validateStorage,validateStorageMonitor,diskHealth,diskKind} from '../lib/proxmox-storage.ts';
const row={key:'a'.repeat(24),name:'remote',node:'pve-amd',type:'cifs',shared:true,remote:true,category:'remote',status:'active',total:1000,used:250,available:750};
const local={...row,key:'b'.repeat(24),name:'local',type:'dir',shared:false,remote:false,category:'local'};
const data=()=>validateStorage({storage:{storage:[row,{...row,node:'pve-nas'},local,{...local,key:'c'.repeat(24),node:'pve-nas'}],nodes:[{name:'pve-amd',online:true},{name:'pve-nas',online:true}],identityComplete:true},updatedAt:1000,stale:false});
const disk={node:'pve-amd',name:'nvme0',model:'Example',size:1000,sizeLabel:'1 KB',health:'healthy',smart:'PASSED',standby:false,temperature:40,wear:2,connection:'nvme',rotation:0};

test('cluster storage regression: shared capacities count once; same-named local volumes count per node',()=>{
 // Symptom: summing node reports triples shared capacity. Cause: one backend reported by every node.
 const scope=storageSelection(data());assert.equal(scope.storage.length,3);
 const totals=storageTotals(scope.storage);assert.equal(totals.remote.total,1000);assert.equal(totals.local.total,2000);
 assert.deepEqual(scope.storage.find(s=>s.shared).nodes,['pve-amd','pve-nas']);
 assert.equal(storageSelection(data(),'pve-amd').storage.length,2);
});
test('storage boundary: inactive shared peer keeps active measurement; missing values stay unknown',()=>{
 const d=data();d.storage[0]={...row,status:'inactive',used:null,total:null,available:null};
 assert.equal(storageTotals(storageSelection(d).storage).remote.used,250);
 assert.deepEqual(storageSelection(d).storage.find(s=>s.shared).unavailableNodes,['pve-amd']);
 const missing=storageSelection({...d,storage:[{...row,total:null,used:null,available:null}]}).storage;
 assert.equal(storageTotals(missing).remote.used,null);assert.equal(storageTotals(missing).remote.incomplete,true);
 assert.equal(storageTotals([]).local.used,0);
});
test('storage rejection: invalid numbers, repeated rows, malformed monitor and node-bound fields',()=>{
 for(const v of [null,{}, {storage:{...data(),storage:[{...row,total:Infinity}]},updatedAt:1,stale:false},{storage:{...data(),storage:[row,row]},updatedAt:1,stale:false}])assert.throws(()=>validateStorage(v));
 assert.throws(()=>validateStorageMonitor({nodes:[{name:'pve-amd',disks:[{...disk,node:'pve-nas'}]}]}));
 assert.throws(()=>validateStorageMonitor({nodes:[{name:'pve-amd',mounts:'bad'}]}));
});
test('monitor normal, boundary and failure: healthy is not inferred for missing or failing SMART',()=>{
 assert.equal(validateStorageMonitor({nodes:[{name:'pve-amd',disks:[disk]}]}).length,1);
 assert.equal(diskHealth(disk),'ok');assert.equal(diskKind(disk),'NVMe');
 assert.equal(diskHealth({...disk,health:null,smart:null}),'unknown');
 assert.equal(diskHealth({...disk,smart:'FAILED'}),'error');
 assert.equal(diskKind({...disk,connection:'usb'}),'USB');
 assert.equal(storageMonitorSelection([{name:'pve-amd'},{name:'old-node'}],data().nodes).length,1);
 assert.deepEqual(storageMonitorSelection([{name:'old-node'}],data().nodes),[]);
 assert.deepEqual(storageMonitorSelection([],[]),[]);
});
await loadBindings();
async function compile(path,replacements={}){
 let {code}=await transform(readFileSync(new URL(path,import.meta.url),'utf8'),{filename:path,jsc:{parser:{syntax:'typescript',tsx:true},target:'es2022',transform:{react:{runtime:'automatic'}}},module:{type:'es6'}});
 for(const name of ['react','react/jsx-runtime'])code=code.replaceAll(`from "${name}"`,`from ${JSON.stringify(import.meta.resolve(name))}`);
 for(const [name,url] of Object.entries(replacements))code=code.replaceAll(`from "${name}"`,`from ${JSON.stringify(url)}`);
 return 'data:text/javascript;base64,'+Buffer.from(code).toString('base64');
}
const guestsURL=await compile('../modules/proxmox/guest-cards.tsx',{'../../lib/proxmox-guests':new URL('../lib/proxmox-guests.ts',import.meta.url).href,'./pve-tag-color':new URL('../modules/proxmox/pve-tag-color.ts',import.meta.url).href});
const ui=await import(await compile('../modules/proxmox/storage-cards.tsx',{'./guest-cards':guestsURL,'../../lib/proxmox-guests':new URL('../lib/proxmox-guests.ts',import.meta.url).href,'../../lib/proxmox-storage':new URL('../lib/proxmox-storage.ts',import.meta.url).href}));
test('actual ProxMenux storage cards: summary, remote badges, capacities, physical health and escaped text',()=>{
 const storage=storageSelection(data()).storage;
 const render=(component,props)=>renderToStaticMarkup(React.createElement(component,props));
 const overview=render(ui.StorageOverview,{storage,disks:[disk]});
 for(const text of ['Storage Used','Local Used','Remote Used','Physical Disks','15.9155','all healthy'])assert.ok(overview.includes(text));
 const list=render(ui.StorageList,{rows:[{...storage[0],names:['<script>test</script>']}]});
 assert.ok(list.includes('remote mount'));assert.ok(list.includes('&lt;script&gt;'));assert.ok(!list.includes('<script>'));
 const incomplete=render(ui.StorageOverview,{storage:[],disks:[],incomplete:true});assert.ok(!incomplete.includes('all healthy'));assert.ok(!incomplete.includes('NaN'));
 const physical=render(ui.PhysicalDisks,{disks:[{...disk,standby:true,temperature:null}],pools:[]});assert.ok(physical.includes('standby'));assert.ok(physical.includes('—'));
});
