import test from 'node:test';
import assert from 'node:assert/strict';
import {parseSearchResponse, searchRequest, externalSearchUrl, searchEngineRequest} from '../lib/search.ts';

const results=[
  {id:'app:1',kind:'app',title:'Jellyfin',description:'Media',url:'https://media.example.test'},
  {id:'dashboard:abc',kind:'dashboard',title:'Werk',description:'Persoonlijk',route:'dashboard',dashboardId:'abc'},
  {id:'module:bookmarks',kind:'module',title:'Bookmarks',description:'Onderdeel',route:'bookmarks'},
];
const engine={id:'engine',revision:1,name:'SearXNG',urlTemplate:'https://search.example.test/search?q=%s'};
test('external search normaal: query escaped as a single value without extra parameters',()=>{
  const url=new URL(externalSearchUrl(engine,'werk & media? #nieuw'));
  assert.equal(url.searchParams.get('q'),'werk & media? #nieuw');assert.equal(Array.from(url.searchParams).length,1);
});
test('external search boundary: Unicode, empty input and path-based templates',()=>{
  assert.equal(new URL(externalSearchUrl(engine,'één 🏠')).searchParams.get('q'),'één 🏠');
  assert.equal(new URL(externalSearchUrl(engine,'')).searchParams.get('q'),'');
  assert.equal(externalSearchUrl({...engine,urlTemplate:'https://example.test/find/%s'},'a/b'),'https://example.test/find/a%2Fb');
});
test('external search faal: unsafe, dynamic or credential-bearing destinations rejected',()=>{
  for(const template of ['javascript:%s','https://%s.example.test','https://example.test?q=%s&other=%s','https://example.test?q=none','https://user:secret@example.test?q=%s','https://example.test?q=%s&api_key=private']) assert.throws(()=>externalSearchUrl({...engine,urlTemplate:template},'query'),TypeError);
  assert.throws(()=>externalSearchUrl(engine,'x'.repeat(201)),TypeError);
});
test('search engine requests normaal: personal list and CSRF-protected revision update',async()=>{
  const original=global.fetch;try{
    global.fetch=async(url,options)=>{assert.equal(url,'/api/search-engines');assert.equal(options.body,undefined);return {ok:true,json:async()=>({engines:[engine]})};};
    assert.deepEqual(await searchEngineRequest(),{engines:[engine]});
    global.fetch=async(url,options)=>{assert.equal(url,'/api/search-engines/engine');assert.equal(options.headers['X-CSRF-Token'],'csrf');assert.equal(JSON.parse(options.body).revision,1);return {ok:true,json:async()=>({engine:{...engine,revision:2}})};};
    await searchEngineRequest('/engine','csrf','PUT',engine);
  }finally{global.fetch=original;}
});
test('search engine requests boundary: empty list and malformed response rejection',async()=>{
  const original=global.fetch;try{
    global.fetch=async()=>({ok:true,json:async()=>({engines:[]})});assert.deepEqual(await searchEngineRequest(),{engines:[]});
    global.fetch=async()=>({ok:true,json:async()=>({engines:[{...engine,revision:0}]})});await assert.rejects(()=>searchEngineRequest(),TypeError);
  }finally{global.fetch=original;}
});
test('search engine requests faal: forbidden, conflict, invalid path and secret URL fail safely',async()=>{
  const original=global.fetch;try{
    global.fetch=async()=>({ok:false,json:async()=>({error:'Elders gewijzigd'})});await assert.rejects(()=>searchEngineRequest(),/Elders gewijzigd/);
    global.fetch=async()=>({ok:false,json:async()=>{throw Error('HTML');}});await assert.rejects(()=>searchEngineRequest(),/niet beschikbaar/);
    global.fetch=async()=>({ok:true,json:async()=>({engines:[{...engine,urlTemplate:'https://user:secret@example.test?q=%s'}]})});await assert.rejects(()=>searchEngineRequest(),TypeError);
    await assert.rejects(()=>searchEngineRequest('/../accounts'),TypeError);
  }finally{global.fetch=original;}
});
test('search response normaal: apps, dashboards, module routes and partial warnings',()=>{
  assert.deepEqual(parseSearchResponse({results,warnings:['Een bron is niet beschikbaar.']}),{results,warnings:['Een bron is niet beschikbaar.']});
});
test('search response boundary: empty result list, 50 matches and subroutes',()=>{
  assert.deepEqual(parseSearchResponse({results:[],warnings:[]}),{results:[],warnings:[]});
  assert.equal(parseSearchResponse({results:Array.from({length:50},(_,id)=>({...results[0],id:`app:${id}`})),warnings:[]}).results.length,50);
  assert.equal(parseSearchResponse({results:[{...results[2],route:'proxmox/nodes'}],warnings:[]}).results[0].route,'proxmox/nodes');
});
test('search response faal: malformed payloads, unsafe destinations and dashboard IDs',()=>{
  for (const payload of [null,{}, {results:[],warnings:[2]}, {results:Array(51).fill(results[0]),warnings:[]},
    {results:[{...results[0],url:'javascript:alert(1)'}],warnings:[]},
    {results:[{...results[0],url:'https://user:secret@example.test'}],warnings:[]},
    {results:[{...results[2],route:'../accounts'}],warnings:[]},
    {results:[{...results[1],dashboardId:'../../other'}],warnings:[]},
    {results:[{...results[0],kind:'unknown'}],warnings:[]}]) assert.throws(()=>parseSearchResponse(payload),TypeError);
});
test('search request normaal: query is encoded once and no credentials enter the URL',async()=>{
  const original=global.fetch;try {
    global.fetch=async(url,options)=>{assert.equal(url,'/api/search?q=werk%20%26%20media');assert.equal(options.cache,'no-store');assert.equal(options.body,undefined);return {ok:true,json:async()=>({results,warnings:[]})};};
    assert.equal((await searchRequest('werk & media')).results.length,3);
  }finally{global.fetch=original;}
});
test('search request boundary: empty query and abort signal forwarded',async()=>{
  const original=global.fetch;const controller=new AbortController();try {
    global.fetch=async(url,options)=>{assert.equal(url,'/api/search?q=');assert.equal(options.signal,controller.signal);return {ok:true,json:async()=>({results:[],warnings:[]})};};
    assert.deepEqual(await searchRequest('',controller.signal),{results:[],warnings:[]});
  }finally{global.fetch=original;}
});
test('search request faal: rejection, invalid JSON, network error and invalid query',async()=>{
  const original=global.fetch;try {
    global.fetch=async()=>({ok:false});await assert.rejects(()=>searchRequest('werk'),/niet beschikbaar/);
    global.fetch=async()=>({ok:true,json:async()=>({results:'invalid',warnings:[]})});await assert.rejects(()=>searchRequest('werk'),TypeError);
    global.fetch=async()=>{throw Error('Offline');};await assert.rejects(()=>searchRequest('werk'),/Offline/);
    for(const query of [null,'x'.repeat(201),'a\nb']) await assert.rejects(()=>searchRequest(query),TypeError);
  }finally{global.fetch=original;}
});
