import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {transform,loadBindings} from 'next/dist/build/swc/index.js';
import {validateInventory,enrichInventory,guestSelection,guestTotals,guestPercent,guestBytes,guestUptime} from '../lib/proxmox-guests.ts';

const guest={vmid:101,node:'pve-amd',name:'Example',type:'lxc',status:'running',tags:'prod',ip:'192.168.20.101',updates:2,cpu:.25,maxcpu:2,mem:1024,maxmem:2048,disk:1024,maxdisk:4096,uptime:300,netin:1000,netout:2000,diskread:50,diskwrite:100};
const nodes=[{name:'pve-amd',online:true,cpu:.5,maxcpu:8,mem:1000,maxmem:2000},{name:'pve-nas',online:true,cpu:.25,maxcpu:24,mem:1000,maxmem:6000}];
const inventory={guests:[guest,{...guest,vmid:102,node:'pve-nas',status:'stopped',type:'qemu'}],nodes};
const data=()=>validateInventory({inventory,updatedAt:1000,stale:false});

test('inventory normal: cluster and node selection, status counts and search',()=>{
 const d=data();assert.equal(guestSelection(d).rows.length,2);
 assert.equal(guestSelection(d,'pve-nas','stopped','102').rows[0].vmid,102);
 assert.equal(guestSelection(d,'pve-amd','running','prod').counts.all,1);
 assert.equal(guestSelection(d,'cluster','running','192.168.20.101').rows.length,1);
});
test('inventory boundary: empty results, unknown measurements and weighted cluster totals',()=>{
 assert.equal(guestSelection(data(),'cluster','running','absent').rows.length,0);
 assert.equal(guestPercent(null,100),null);assert.equal(guestPercent(50,0),null);
 assert.equal(guestBytes(null),'—');assert.equal(guestBytes(0),'0 B');assert.equal(guestUptime(90060),'1d 1h 1m');
 assert.equal(guestTotals([],nodes).cpuPercent,31.25); // (8*.5 + 24*.25) / 32, never average node percentages.
 assert.equal(guestTotals([],[]).cpuPercent,null);
 assert.equal(guestTotals([guest],[{...nodes[0],maxmem:null}]).memoryPercent,null);
});
test('inventory rejection: malformed payload, nonfinite metrics, duplicate identity',()=>{
 for(const value of [null,{}, {inventory,updatedAt:NaN,stale:false},{inventory:{...inventory,guests:[guest,guest]},updatedAt:1,stale:false},{inventory:{...inventory,guests:[{...guest,cpu:Infinity}]},updatedAt:1,stale:false}])assert.throws(()=>validateInventory(value));
});
test('monitor enrichment normal and failure: node-bound identity, stale and migrated rows cannot override inventory',()=>{
 const raw=data(),monitor={nodes:[{name:'pve-amd',guests:[{...guest,netin:5000}]}]};
 assert.equal(enrichInventory(raw,monitor).guests[0].netin,5000);
 for(const n of [{...monitor.nodes[0],stale:true},{...monitor.nodes[0],error:'offline'},{name:'pve-nas',guests:[{...guest,netin:999}]}])assert.equal(enrichInventory(raw,{nodes:[n]}).guests[0].netin,1000);
 assert.deepEqual(enrichInventory(raw,null),raw);
 assert.equal(enrichInventory(raw,{nodes:[{name:'pve-amd',guests:[{...guest,status:'stopped',netin:900}]}]}).guests[0].netin,1000);
});

await loadBindings();
let {code}=await transform(readFileSync(new URL('../modules/proxmox/guest-cards.tsx',import.meta.url),'utf8'),{filename:'guest-cards.tsx',jsc:{parser:{syntax:'typescript',tsx:true},target:'es2022',transform:{react:{runtime:'automatic'}}},module:{type:'es6'}});
for(const name of ['react','react/jsx-runtime'])code=code.replaceAll(`from "${name}"`,`from ${JSON.stringify(import.meta.resolve(name))}`);
code=code.replace('from "../../lib/proxmox-guests"',`from ${JSON.stringify(new URL('../lib/proxmox-guests.ts',import.meta.url).href)}`).replace('from "./pve-tag-color"',`from ${JSON.stringify(new URL('../modules/proxmox/pve-tag-color.ts',import.meta.url).href)}`);
const {GuestCard,GuestOverview}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
test('actual ProxMenux-derived cards: four summaries, donut, five metrics, tags and update count',()=>{
 const overview=renderToStaticMarkup(React.createElement(GuestOverview,{guests:inventory.guests,nodes}));
 for(const title of ['Total VMs &amp; LXCs','Total CPU Allocated','Total Memory','Total Disk'])assert.ok(overview.includes(title));
 assert.ok(overview.includes('15.9155'));
 const card=renderToStaticMarkup(React.createElement(GuestCard,{guest}));
 for(const text of ['CPU Usage','Memory','Disk Usage','Disk I/O','Network I/O','192.168.20.101','pve-amd','prod'])assert.ok(card.includes(text));
 assert.ok(!card.includes('NaN'));
});
test('cards boundary and rejection: unknown values stay unknown and names are escaped',()=>{
 const card=renderToStaticMarkup(React.createElement(GuestCard,{guest:{...guest,name:'<script>alert(1)</script>',cpu:null,mem:null,disk:null}}));
 assert.ok(card.includes('&lt;script&gt;'));assert.ok(!card.includes('<script>'));assert.ok(card.includes('—'));assert.ok(!card.includes('NaN'));
});
