import test from 'node:test';
import assert from 'node:assert/strict';
import {requestBookmarkLogin} from '../lib/bookmark-logins.ts';

test('bookmark login normaal: only ID and CSRF, no selected destination or credentials',async()=>{
 const previous=globalThis.fetch;
 try {globalThis.fetch=async(path,options)=>{assert.equal(path,'/api/bookmark-logins/42/launch');assert.equal(options.body,'{}');assert.equal(options.headers['X-CSRF-Token'],'csrf');assert.equal(options.cache,'no-store');return {ok:true,json:async()=>({url:'https://app.example.test/sso'})};};assert.equal(await requestBookmarkLogin(42,'csrf','https://app.example.test'),'https://app.example.test/sso');}
 finally {globalThis.fetch=previous;}
});

test('bookmark login boundary: login ticket fragment stays on exact configured origin',async()=>{
 const previous=globalThis.fetch;
 try {globalThis.fetch=async()=>({ok:true,json:async()=>({url:'https://app.example.test:8443/#/connect/login/dash/a/b'})});assert.match(await requestBookmarkLogin(1,'csrf','https://app.example.test:8443'),/connect\/login/);await assert.rejects(requestBookmarkLogin(0,'csrf','https://app.example.test'));await assert.rejects(requestBookmarkLogin(Number.MAX_SAFE_INTEGER+1,'csrf','https://app.example.test'));}
 finally {globalThis.fetch=previous;}
});

test('bookmark login faal: reject foreign origins, HTTP, credentials and failed API responses',async()=>{
 const previous=globalThis.fetch;
 try {
  for(const url of ['https://foreign.example.test/login','http://app.example.test/login','https://user:password@app.example.test/login','javascript:alert(1)']) {globalThis.fetch=async()=>({ok:true,json:async()=>({url})});await assert.rejects(requestBookmarkLogin(1,'csrf','https://app.example.test'));}
  globalThis.fetch=async()=>({ok:false,json:async()=>({error:'Geen toegang.'})});await assert.rejects(requestBookmarkLogin(1,'csrf','https://app.example.test'),/Geen toegang/);
  globalThis.fetch=async()=>({ok:true,json:async()=>({})});await assert.rejects(requestBookmarkLogin(1,'csrf','https://app.example.test'));
 }finally {globalThis.fetch=previous;}
});
