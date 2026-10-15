import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {transform,loadBindings} from 'next/dist/build/swc/index.js';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {metricRows,metricSetting,metricEndpoint,loadMetric} from '../modules/system/metrics.ts';
import {moduleOptions} from '../lib/dashboard-modules.ts';

await loadBindings();
let {code}=await transform(readFileSync(new URL('../modules/system/cards.tsx',import.meta.url),'utf8'),{filename:'cards.tsx',jsc:{parser:{syntax:'typescript',tsx:true},target:'es2022',transform:{react:{runtime:'automatic'}}},module:{type:'es6'}});
code=code.replaceAll('from "react/jsx-runtime"',`from ${JSON.stringify(import.meta.resolve('react/jsx-runtime'))}`)
 .replace('from "./metrics"',`from ${JSON.stringify(new URL('../modules/system/metrics.ts',import.meta.url).href)}`)
 .replace('from "../../lib/proxmox"',`from ${JSON.stringify(new URL('../lib/proxmox.ts',import.meta.url).href)}`);
const {SystemCards}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
const cluster={summary:{nodesByCpu:[{name:'b',cpu:0},{name:'a',cpu:95}],nodesByMemory:[{name:'a',memory:50}],offlineNodes:[]},stale:false};
const monitor={nodes:[{name:'a',temperature:62,powerWatts:0,stale:false}]};
const render=(metric,rows)=>renderToStaticMarkup(React.createElement(SystemCards,{metric,rows}));

test('system widget normal: four real measurements, node selection and independent configuration',()=>{
 assert.equal(moduleOptions(['proxmox']).find(m=>m.id==='system').settings.metric,'cpu');
 assert.equal(metricSetting('power'),'power');
 assert.deepEqual(metricRows('cpu',cluster).map(row=>row.name),['a','b']);
 assert.equal(metricRows('cpu',cluster,'b')[0].value,0);
 assert.equal(metricRows('memory',cluster)[0].value,50);
 assert.equal(metricRows('temperature',monitor)[0].value,62);
 assert.equal(metricRows('power',monitor)[0].value,0);
 assert.match(render('cpu',metricRows('cpu',cluster,'a')),/Zeer hoog gebruik/);
 assert.match(render('power',metricRows('power',monitor)),/geen totaalverbruik/);
 assert.match(render('cpu',metricRows('cpu',cluster)),/stroke-dasharray="95 100"/);
});
test('system widget boundary: empty sources, missing node, unknown values, offline and stale readings',()=>{
 assert.deepEqual(metricRows('temperature',{nodes:[]}),[]);
 assert.deepEqual(metricRows('cpu',cluster,'removed'),[]);
 const unknown=metricRows('temperature',{nodes:[{name:'a',temperature:null,stale:true,error:'timeout'}]});
 const html=render('temperature',unknown);assert.match(html,/Verouderd/);assert.match(html,/—/);assert.doesNotMatch(html,/0.*°C/);
 assert.equal(metricRows('cpu',{...cluster,summary:{...cluster.summary,offlineNodes:['a']}})[0].value,null);
 for(const v of [NaN,Infinity,-1,101,'50'])assert.equal(metricRows('cpu',{summary:{nodesByCpu:[{name:'a',cpu:v}]}})[0].value,null);
 assert.equal(metricRows('memory',{summary:{nodesByMemory:[{name:'a',memory:100}]}})[0].value,100);
 assert.deepEqual(moduleOptions(['dashboard']).filter(m=>m.id==='system'),[]);
});
test('system widget failure: reject malformed data, unsafe setting names and escape source text',()=>{
 for(const v of [null,{},true,'constructor','invalid'])assert.throws(()=>metricSetting(v));
 for(const value of [null,{}, {nodes:{}},{nodes:[null]},{nodes:[{name:''}]},{nodes:Array.from({length:17},()=>({name:'a'}))}])assert.throws(()=>metricRows('power',value));
 assert.doesNotMatch(render('power',metricRows('power',{nodes:[{name:'<script>x</script>',powerWatts:42}]})),/<script>/);
});
test('system source normal: fixed authenticated routes and no upstream address from settings',async()=>{
 const calls=[];const signal=new AbortController().signal;
 const result=await loadMetric('cpu','b',signal,async(path,options)=>{calls.push([path,options]);return new Response(JSON.stringify(cluster));});
 assert.equal(result[0].value,0);assert.equal(calls[0][0],'/api/proxmox/summary');assert.equal(calls[0][1].signal,signal);
 assert.equal(metricEndpoint('power'),'/api/proxmenux/summary');
 assert.deepEqual(await loadMetric('power','',signal,async()=>new Response('{"nodes":[]}')),[]);
});
// Regression: parameter properties prevented Node's strip-only test runtime from loading the error class.
test('system source failure and authorization: safe errors distinguish denied access for removing cached readings',async()=>{
 const signal=new AbortController().signal;
 for(const status of [401,403])await assert.rejects(loadMetric('cpu','',signal,async()=>new Response('secret upstream',{status})),e=>e.denied===true&&!e.message.includes('secret'));
 for(const status of [409,500])await assert.rejects(loadMetric('cpu','',signal,async()=>new Response('secret upstream',{status})),e=>!e.denied&&!e.message.includes('secret'));
 await assert.rejects(loadMetric('cpu','',signal,async()=>{throw new Error('secret transport');}),/tijdelijk niet bereikbaar/);
 await assert.rejects(loadMetric('cpu','',signal,async()=>new Response('invalid json')),/Geen geldige systeemgegevens/);
});
