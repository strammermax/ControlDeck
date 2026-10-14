import test from 'node:test';
import assert from 'node:assert/strict';
import {requestAppLaunch} from '../lib/app-launches.ts';

test('app launch normal: CSRF request has no browser-selected account, credentials or destination',async()=>{
 const previous=globalThis.fetch;
 try {globalThis.fetch=async(url,options)=>{assert.equal(url,'/api/app-launches/kasm');assert.equal(options.method,'POST');assert.equal(options.cache,'no-store');assert.equal(options.body,'{}');assert.equal(options.headers['X-CSRF-Token'],'csrf');return {ok:true,json:async()=>({url:'https://kasm.example.test/#/connect/login/dash/a/b'})};};assert.equal(await requestAppLaunch('kasm','csrf'),'https://kasm.example.test/#/connect/login/dash/a/b');}
 finally {globalThis.fetch=previous;}
});
test('app launch boundary: Nextcloud follows configured login route',async()=>{
 const previous=globalThis.fetch;
 try {globalThis.fetch=async()=>({ok:true,json:async()=>({url:'https://cloud.example.test/apps/user_oidc/login/1'})});assert.match(await requestAppLaunch('nextcloud','csrf'),/user_oidc/);}
 finally {globalThis.fetch=previous;}
});
test('app launch failure: unknown adapters, refused access, unsafe links and malformed responses',async()=>{
 const previous=globalThis.fetch;
 try {
  await assert.rejects(requestAppLaunch('unknown','csrf'));
  for(const result of [{ok:false,json:async()=>({error:'Geen toegang.'})},{ok:true,json:async()=>({})},{ok:true,json:async()=>({url:'javascript:alert(1)'})},{ok:true,json:async()=>({url:'https://u:p@example.test'})}]) {globalThis.fetch=async()=>result;await assert.rejects(requestAppLaunch('kasm','csrf'));}
 } finally {globalThis.fetch=previous;}
});
