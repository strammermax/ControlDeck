import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {loadBindings,transform} from 'next/dist/build/swc/index.js';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {serviceWidgets,widgetPath,safeEmbed,offerLink,widgetDate,widgetRequest,validateWidgetData,validateWidgetSources} from '../lib/service-widgets.ts';
import {moduleOptions} from '../lib/dashboard-modules.ts';

await loadBindings();
let {code}=await transform(readFileSync(new URL('../modules/service/cards.tsx',import.meta.url),'utf8'),{filename:'cards.tsx',jsc:{parser:{syntax:'typescript',tsx:true},target:'es2022',transform:{react:{runtime:'automatic'}}},module:{type:'es6'}});
code=code.replaceAll('from "react/jsx-runtime"',`from ${JSON.stringify(import.meta.resolve('react/jsx-runtime'))}`).replace('from "../../lib/service-widgets"',`from ${JSON.stringify(new URL('../lib/service-widgets.ts',import.meta.url).href)}`);
const {ServiceCards}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
const empty={items:[],stats:[],updatedAt:null,stale:false};
const render=data=>renderToStaticMarkup(React.createElement(ServiceCards,{data}));

// Regression: malformed normalized responses or source lists could crash the widget render.
test('widget response validation normal, boundary and rejection before rendering',()=>{
 assert.deepEqual(validateWidgetData(empty),empty);
 assert.equal(validateWidgetData({embedUrl:'https://ha.example.test/lovelace/room'}).title,'Home Assistant');
 assert.deepEqual(validateWidgetSources({sources:[]}),[]);
 const source={id:'queue',title:'Downloads',kind:'sabnzbd'};
 assert.deepEqual(validateWidgetSources({sources:[source]}),[source]);
 for(const value of [null,{}, {...empty,items:[null]}, {...empty,updatedAt:-1},{...empty,items:Array(51).fill({})},{...empty,items:[{id:'1',title:'One',subtitle:'',status:'',progress:101}]},{embedUrl:'http://ha.example.test'}])assert.throws(()=>validateWidgetData(value));
 for(const value of [null,{sources:null},{sources:[{}]},{sources:[source,source]},{sources:[{...source,id:'../secret'}]}])assert.throws(()=>validateWidgetSources(value));
});

// Regression: extensionless catalog imports failed in Node's strip-only test runner.
test('service widgets normal: each family is independently configurable with existing source permission',()=>{
 assert.equal(serviceWidgets.length,6);
 // Regression: the HA default height exceeded the dashboard's six-row maximum and could not be saved.
 for(const module of serviceWidgets){assert.ok(module.height>=1&&module.height<=6);assert.ok(module.width>=1&&module.width<=12);assert.equal(module.settings.sourceId,'');assert.ok(moduleOptions([module.permission]).some(m=>m.id===module.id));assert.equal(widgetPath(module.id,'source-1'),`/api/widgets/${module.id}/source-1`);}
 assert.equal(moduleOptions(['dashboard']).filter(m=>serviceWidgets.some(s=>s.id===m.id)).length,0);
});
test('service cards normal: queue progress, stream status, offers and source timestamps',()=>{
 const html=render({...empty,updatedAt:1000,items:[{id:'1',title:'Movie',subtitle:'Series',status:'Playing',progress:50,date:'2026-10-14T10:00:00Z'},{id:'2',title:'Nieuwe aanbieding',subtitle:'Marktplaats',status:'Nieuw',url:'https://offers.example.test/item/2',priceCents:1250,currency:'EUR'}],stats:[{label:'Workers',value:'2'}]});
 assert.match(html,/<progress max="100" value="50"/);assert.match(html,/Playing/);assert.match(html,/12,50/);assert.match(html,/rel="noopener noreferrer"/);assert.match(html,/Workers/);
});
test('service cards boundary: pending, empty, stale, missing price and invalid date',()=>{
 assert.match(render(empty),/Geen items/);assert.match(render({...empty,pending:true}),/Nog geen statistieken/);
 assert.match(render({...empty,stale:true}),/verouderd/);
 assert.match(render({...empty,items:[{id:'1',title:'One',subtitle:'',status:'',priceCents:null}]}),/Prijs niet vermeld/);
 assert.equal(widgetDate('invalid'),'Tijdstip onbekend');assert.ok(widgetDate('2026-10-14',true).includes('2026'));
});
test('Home Assistant iframe normal: HTTPS dashboard, sandbox and separate login fallback',()=>{
 const html=render({...empty,embedUrl:'https://ha.example.test/lovelace/slaapkamer-paneel',title:'Slaapkamer'});
 assert.match(html,/<iframe/);assert.match(html,/title="Slaapkamer"/);assert.match(html,/sandbox="allow-scripts allow-same-origin allow-forms allow-popups"/);assert.match(html,/referrerPolicy="no-referrer"/);assert.match(html,/eigen aanmelding/);
});
test('widget failure: no credentials, script URLs, mixed-content frames or HTML injection',()=>{
 for(const url of ['http://ha.example.test','javascript:alert(1)','https://user:pass@ha.example.test','https://ha.example.test/?token=secret'])assert.throws(()=>safeEmbed(url));
 for(const url of ['javascript:alert(1)','https://user:pass@offers.example.test'])assert.throws(()=>offerLink(url));
 for(const id of ['../source','TOKEN','a'.repeat(65),''])assert.throws(()=>widgetPath('downloads',id));
 assert.doesNotMatch(render({...empty,items:[{id:'1',title:'<script>bad</script>',subtitle:'',status:''}]}),/<script>/);
});
test('widget API normal, boundary and authorization failures are safe and never return upstream error bodies',async()=>{
 const signal=new AbortController().signal;
 assert.deepEqual(await widgetRequest('/api/widgets/downloads/source',signal,async()=>new Response(JSON.stringify(empty))),empty);
 for(const status of [401,403,404,503])await assert.rejects(widgetRequest('/api/widgets/downloads/source',signal,async()=>new Response('secret credentials',{status})),e=>!e.message.includes('secret')&&e.denied===[401,403,404].includes(status));
 await assert.rejects(widgetRequest('/api/widgets/downloads/source',signal,async()=>new Response('bad json')),/Ongeldig antwoord/);
 await assert.rejects(widgetRequest('/api/widgets/downloads/source',signal,async()=>{throw new Error('secret');}),/niet bereikbaar/);
});
