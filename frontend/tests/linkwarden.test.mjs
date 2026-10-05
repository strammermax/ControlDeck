import test from 'node:test';
import assert from 'node:assert/strict';
import {linkwardenRequest,guidedLxcSteps,LINKWARDEN_LXC_COMMAND} from '../lib/linkwarden.ts';

test('Linkwarden normaal: personal token uses protected CSRF endpoint',async()=>{
  const previous=globalThis.fetch;
  try{globalThis.fetch=async(url,options)=>{assert.equal(url,'/api/linkwarden/token');assert.equal(options.method,'PUT');assert.equal(options.headers['X-CSRF-Token'],'csrf');assert.equal(JSON.parse(options.body).token,'personal');return {ok:true,json:async()=>({connected:true})};};assert.equal((await linkwardenRequest('/token','csrf','PUT',{token:'personal'})).connected,true);}finally{globalThis.fetch=previous;}
});
test('Linkwarden boundary: empty search result is usable without mutations',async()=>{
  const previous=globalThis.fetch;
  try{globalThis.fetch=async(_,options)=>{assert.equal(options.method,'GET');assert.equal(options.body,undefined);return {ok:true,json:async()=>({links:[],nextCursor:null})};};assert.deepEqual((await linkwardenRequest('/bookmarks','csrf')).links,[]);}finally{globalThis.fetch=previous;}
});
test('Linkwarden faal: unauthorized and malformed responses are rejected',async()=>{
  const previous=globalThis.fetch;
  try{globalThis.fetch=async()=>({ok:false,json:async()=>({error:'Geen toegang'})});await assert.rejects(linkwardenRequest('/bookmarks','csrf'),/Geen toegang/);globalThis.fetch=async()=>({ok:true,json:async()=>null});await assert.rejects(linkwardenRequest('/bookmarks','csrf'),/niet beschikbaar/);}finally{globalThis.fetch=previous;}
});

test('LXC guide normaal: selects a node and uses the official fixed script',()=>{
  assert.match(guidedLxcSteps('pve-amd')[0],/pve-amd/);
  assert.match(LINKWARDEN_LXC_COMMAND,/community-scripts\/ProxmoxVE\/main\/ct\/linkwarden.sh/);
  assert.ok(guidedLxcSteps('pve-amd').some(step=>step.includes('API-token')));
});
test('LXC guide boundary: shortest and longest node names are accepted',()=>{
  assert.equal(guidedLxcSteps('a').length,5);
  assert.equal(guidedLxcSteps('a'.repeat(63)).length,5);
});
test('LXC guide faal: empty, malformed and command-like node names are rejected',()=>{
  for(const value of ['', 'a'.repeat(64),'pve;echo x','$(id)','pve node'])assert.throws(()=>guidedLxcSteps(value),/geldige/);
});
