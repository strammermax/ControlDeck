import test from 'node:test';
import assert from 'node:assert/strict';
import {installationRequest} from '../lib/installations.ts';

test('wizard normaal: review and install use the admin API and CSRF',async()=>{
  const previous=globalThis.fetch;
  try {
    globalThis.fetch=async(url,options)=>{
      assert.equal(url,'/api/installations/plan');assert.equal(options.method,'POST');assert.equal(options.headers['X-CSRF-Token'],'csrf');
      assert.equal(JSON.parse(options.body).module,'termix');return {ok:true,json:async()=>({canInstall:true})};
    };
    assert.equal((await installationRequest('/plan','csrf',{module:'termix',method:'docker',target:'local'})).canInstall,true);
  } finally{globalThis.fetch=previous;}
});
test('wizard boundary: status reads have no mutation or CSRF payload',async()=>{
  const previous=globalThis.fetch;
  try {
    globalThis.fetch=async(_,options)=>{assert.equal(options.method,'GET');assert.equal(options.body,undefined);return {ok:true,json:async()=>({status:'queued'})};};
    assert.equal((await installationRequest('/jobs/id','csrf')).status,'queued');
  } finally{globalThis.fetch=previous;}
});
test('wizard faal: backend rejection and malformed response are shown',async()=>{
  const previous=globalThis.fetch;
  try {
    globalThis.fetch=async()=>({ok:false,json:async()=>({error:'Beheerrechten vereist'})});
    await assert.rejects(installationRequest('','csrf'),/Beheerrechten/);
    globalThis.fetch=async()=>({ok:true,json:async()=>null});
    await assert.rejects(installationRequest('','csrf'),/Ongeldig/);
  } finally{globalThis.fetch=previous;}
});
import { modulesFor } from '../lib/installations.ts';
const catalog = [{id:'termix',installed:true},{id:'proxmox',installed:true},{id:'proxmenux',installed:false}];
test('modulesFor / normaal: install hides installed modules; edit and remove show only installed', () => {
  assert.deepEqual(modulesFor('install',catalog).map(m => m.id),['proxmenux']);
  assert.deepEqual(modulesFor('edit',catalog).map(m => m.id),['termix','proxmox']);
  assert.deepEqual(modulesFor('remove',catalog).map(m => m.id),['termix','proxmox']);
});
test('modulesFor / boundary: everything or nothing installed', () => {
  assert.deepEqual(modulesFor('install',catalog.map(m => ({...m,installed:true}))),[]);
  assert.deepEqual(modulesFor('remove',[]),[]);
});
test('modulesFor / faal: unknown state is never offered for edit or removal', () => {
  assert.deepEqual(modulesFor('remove',[{id:'x'}]),[]);
  assert.deepEqual(modulesFor('install',[{id:'x'}]).map(m => m.id),['x']);
  assert.throws(() => modulesFor('install',null),TypeError);
});
