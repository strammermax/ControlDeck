import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {transform,loadBindings} from 'next/dist/build/swc/index.js';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {validateTrafficHistory,trafficSeries,trafficTotals,trafficTick} from '../lib/proxmox-network-history.ts';
const rate=1024**3/300;
const node={name:'pve-amd',historyAvailable:true,timeframe:'day',step:300,history:[{time:600,received:rate,sent:0},{time:900,received:rate*2,sent:rate}]};
test('traffic normal: align cluster nodes before summing, period is node-independent',()=>{
 const nodes=validateTrafficHistory({nodes:[node,{...node,name:'pve-nas'}]},'day');
 const series=trafficSeries(nodes,['pve-amd','pve-nas'],'day');
 assert.equal(series.step,300);assert.equal(series.incomplete,false);assert.equal(series.points[0].received,2);assert.equal(series.points[1].sent,2);
 assert.equal(trafficSeries(nodes,['pve-amd'],'day').points[0].received,1);
 assert.equal(trafficSeries(nodes,['pve-amd'],'hour').points.length,0);
 const shifted={...node,name:'pve-nas',history:[...node.history,{time:1200,received:rate,sent:0}]};assert.equal(trafficSeries([node,shifted],['pve-amd','pve-nas'],'day').points.length,2);
});
test('traffic first-interval regression: ProxMenux hardcoded 60 seconds for the first five-minute sample',()=>{
 const series=trafficSeries([node],['pve-amd'],'day');
 assert.equal(series.points[0].received,1);assert.equal(series.points[1].received,2);
});
test('traffic boundary: mixed 60/300-second sampling, nulls, zero and missing nodes remain explicit',()=>{
 const fine={...node,name:'pve-nas',step:60,history:Array.from({length:10},(_,i)=>({time:360+i*60,received:rate,sent:0}))};
 const aligned=trafficSeries([node,fine],['pve-amd','pve-nas'],'day');assert.equal(aligned.points.find(p=>p.time===600).received,2);
 const missing=trafficSeries([node],['pve-amd','pve-nas'],'day');assert.equal(missing.points[0].received,null);assert.equal(missing.incomplete,true);
 const gap=trafficSeries([{...node,history:[node.history[0],{time:1200,received:null,sent:0}]}],['pve-amd'],'day');
 assert.equal(gap.points.find(p=>p.time===900).received,null);assert.equal(gap.points.at(-1).sent,0);assert.equal(gap.points.at(-1).received,null);
 assert.equal(trafficSeries([],[],'day').points.length,0);
 assert.equal(trafficSeries([{...node,stale:true}],['pve-amd'],'day').incomplete,true);
 assert.ok(trafficTick(1792328400,'day').length>0);
});
test('traffic rejection: duplicate node/sample, wrong period, invalid interval and nonfinite/negative values',()=>{
 for(const value of [null,{}, {nodes:[node,node]},{nodes:[{...node,timeframe:'hour'}]},{nodes:[{...node,step:0}]},{nodes:[{...node,history:[node.history[0],node.history[0]]}]},{nodes:[{...node,history:[{...node.history[0],received:Infinity}]}]},{nodes:[{...node,history:[{...node.history[0],sent:-1}]}]}])assert.throws(()=>validateTrafficHistory(value,'day'));
 assert.equal(validateTrafficHistory({nodes:[{name:'pve-amd',loading:true}]},'day').length,1);
});
await loadBindings();
async function compile(path,replacements={}){
 let {code}=await transform(readFileSync(new URL(path,import.meta.url),'utf8'),{filename:path,jsc:{parser:{syntax:'typescript',tsx:true},target:'es2022',transform:{react:{runtime:'automatic'}}},module:{type:'es6'}});
 for(const name of ['react','react/jsx-runtime','recharts'])code=code.replaceAll(`from "${name}"`,`from ${JSON.stringify(import.meta.resolve(name))}`);
 for(const [name,url] of Object.entries(replacements))code=code.replaceAll(`from "${name}"`,`from ${JSON.stringify(url)}`);
 return 'data:text/javascript;base64,'+Buffer.from(code).toString('base64');
}
const shared=await compile('../modules/proxmox/guest-cards.tsx',{'../../lib/proxmox-guests':new URL('../lib/proxmox-guests.ts',import.meta.url).href,'./pve-tag-color':new URL('../modules/proxmox/pve-tag-color.ts',import.meta.url).href});
const ui=await import(await compile('../modules/proxmox/network-traffic-chart.tsx',{'./guest-cards':shared,'../../lib/proxmox-network-history':new URL('../lib/proxmox-network-history.ts',import.meta.url).href}));
const render=(component,props)=>renderToStaticMarkup(React.createElement(component,props));
test('actual traffic chart normal, boundary and failure UI: period selector, accessible legend and safe tooltip',()=>{
 const html=render(ui.NetworkTrafficChart,{names:['pve-amd']});for(const value of ['Network Traffic','24 uur','1 uur','7 dagen','30 dagen','1 jaar','Periode netwerkverkeer'])assert.ok(html.includes(value),value);
 const plot=render(ui.TrafficPlot,{points:trafficSeries([node],['pve-amd'],'day').points,period:'day'});assert.ok(plot.includes('Received'));assert.ok(plot.includes('Sent'));assert.equal((plot.match(/aria-pressed="true"/g)||[]).length,2);
 assert.equal(render(ui.TrafficTooltip,{active:false,payload:[]}), '');
 const tooltip=render(ui.TrafficTooltip,{active:true,label:600,payload:[{name:'<script>bad</script>',value:1}]});assert.ok(tooltip.includes('1.000 GB'));assert.ok(tooltip.includes('&lt;script&gt;'));assert.ok(!tooltip.includes('<script>'));
});

test('period summary regression: lifetime counters previously disagreed with the selected chart period and node',()=>{
 const sources=[node,{...node,name:'pve-nas'}];
 assert.deepEqual(trafficTotals(trafficSeries(sources,['pve-amd'],'day').points),{received:3*1024**3,sent:1024**3});
 assert.equal(trafficTotals(trafficSeries(sources,['pve-amd','pve-nas'],'day').points).received,6*1024**3);
 assert.deepEqual(trafficTotals([{time:1,received:0,sent:0}]),{received:0,sent:0});
 assert.deepEqual(trafficTotals([]),{received:null,sent:null});
 assert.equal(trafficTotals(trafficSeries(sources,['pve-amd'],'hour').points).received,null);
 assert.equal(trafficTotals([{time:1,received:null,sent:0}]).received,null);
 assert.deepEqual(trafficTotals([{time:1,received:1,sent:1}],true),{received:null,sent:null});
});
test('shared summary normal and loading UI: default period and unknown totals are passed in the same render',()=>{
 let summary;
 render(ui.NetworkTrafficChart,{names:['pve-amd'],overview:value=>{summary=value;return React.createElement('p',null,value.label);}});
 assert.deepEqual(summary,{received:null,sent:null,label:'24 uur · laden…'});
});
