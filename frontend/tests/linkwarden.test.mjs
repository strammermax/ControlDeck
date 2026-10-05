import test from 'node:test';
import assert from 'node:assert/strict';
import {linkwardenRequest} from '../lib/linkwarden.ts';

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
