import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {transform,loadBindings} from 'next/dist/build/swc/index.js';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {proxmoxView} from '../modules/proxmox/settings.ts';
import {moduleOptions} from '../lib/dashboard-modules.ts';

// Exercise actual shared JSX with server rendering; effects do not contact live services.
const file=new URL('../components/proxmox-summary.tsx',import.meta.url);
await loadBindings();
let {code:js}=await transform(readFileSync(file,'utf8'),{filename:'proxmox-summary.tsx',jsc:{parser:{syntax:'typescript',tsx:true},target:'es2022',transform:{react:{runtime:'automatic'}}},module:{type:'es6'}});
for(const name of ['react','react/jsx-runtime']) js=js.replaceAll(`from "${name}"`,`from ${JSON.stringify(import.meta.resolve(name))}`);
js=js.replace('from "../lib/proxmox"',`from ${JSON.stringify(new URL('../lib/proxmox.ts',import.meta.url).href)}`);
const {ProxmoxSummaryContent,ProxmoxSummary}=await import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'));
let {code:healthJs}=await transform(readFileSync(new URL('../components/proxmenux-health.tsx',import.meta.url),'utf8'),{filename:'proxmenux-health.tsx',jsc:{parser:{syntax:'typescript',tsx:true},target:'es2022',transform:{react:{runtime:'automatic'}}},module:{type:'es6'}});
for(const name of ['react','react/jsx-runtime']) healthJs=healthJs.replaceAll(`from "${name}"`,`from ${JSON.stringify(import.meta.resolve(name))}`);
healthJs=healthJs.replace('from "../lib/proxmox"',`from ${JSON.stringify(new URL('../lib/proxmox.ts',import.meta.url).href)}`);
const {ProxmenuxHealthContent}=await import('data:text/javascript;base64,'+Buffer.from(healthJs).toString('base64'));
const data={updatedAt:1000,stale:false,summary:{guests:[],nodesByCpu:[{name:'node-test',cpu:20,cpus:4}],nodesByMemory:[{name:'node-test',memory:50,memoryUsed:1024,memoryTotal:2048}],offlineNodes:[],taskCategories:{backup:{ok:1,error:2,warning:0}},taskNodes:{},sdnZones:{total:0},windowHours:24}};
const render=(extra={})=>renderToStaticMarkup(React.createElement(ProxmoxSummaryContent,{data,...extra}));

test('Proxmox module normal: selectable existing source and actual node cards',()=>{
 assert.equal(moduleOptions(['proxmox'])[0].id,'proxmox');
 assert.equal(proxmoxView('health'),'health');
 const html=render({view:'nodes',embedded:true});
 assert.match(html,/node-test/);assert.match(html,/20.0 %/);assert.match(html,/50.0 %/);
 assert.doesNotMatch(html,/Taken per categorie/);assert.match(html,/Bijgewerkt/);
});
test('Proxmox module boundary: empty guests, complete overview and loading',()=>{
 assert.match(render({view:'guests'}),/Geen draaiende gasten/);
 assert.doesNotMatch(render({view:'guests'}),/node-test/);
 assert.match(render(),/SDN-zones/);
 assert.match(renderToStaticMarkup(React.createElement(ProxmoxSummary,{refreshSeconds:60,embedded:true})),/Proxmox laden/);
});
test('Proxmox module failure: stale values retain warning and offline node names are escaped',()=>{
 const html=render({view:'tasks',error:'Bron tijdelijk onbereikbaar',data:{...data,stale:true,summary:{...data.summary,offlineNodes:['<script>bad</script>']}}});
 assert.match(html,/Bron tijdelijk onbereikbaar/);assert.match(html,/laatst bekende/);
 assert.match(html,/Backups/);assert.doesNotMatch(html,/<script>/);
 for(const value of [null,undefined,'',true,{},'constructor','token'])assert.throws(()=>proxmoxView(value));
 assert.deepEqual(moduleOptions(['dashboard']),[]);
});

test('ProxMenux compact normal: reuse node health, sensors and problem reasons',()=>{
 const html=renderToStaticMarkup(React.createElement(ProxmenuxHealthContent,{compact:true,nodes:[{name:'node-test',overall:'warning',stale:false,updatedAt:1000,temperature:65,powerWatts:42,load:1.2,hostUpdates:3,categories:[{id:'memory',status:'warning',reason:'Veel geheugen in gebruik'}]}]}));
 assert.match(html,/65 °C/);assert.match(html,/42 W/);assert.match(html,/Veel geheugen in gebruik/);
 assert.doesNotMatch(html,/LXC-updates/);assert.doesNotMatch(html,/PVE LXC Updater/);
});
test('ProxMenux compact boundary and failure: empty source and unavailable sensors remain explicit',()=>{
 assert.match(renderToStaticMarkup(React.createElement(ProxmenuxHealthContent,{compact:true,nodes:[]})),/Geen monitornodes/);
 const html=renderToStaticMarkup(React.createElement(ProxmenuxHealthContent,{compact:true,nodes:[{name:'node-test',overall:'unknown',stale:true,error:'Monitor onbereikbaar',partial:['hardware'],updatedAt:1000}]}));
 assert.match(html,/Monitor onbereikbaar/);assert.match(html,/laatst bekende/);assert.match(html,/Niet beschikbaar: hardware/);
 assert.doesNotMatch(html,/0 °C/);
});
