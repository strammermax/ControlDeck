import assert from 'node:assert/strict';
import { test } from 'node:test';
import { agentRows, agentStateText } from '../lib/cronjobs.ts';

test('agentRows / normaal: enrolled nodes keep their state, Proxmox suggestions fill the rest', () => {
  const rows = agentRows({proxy:true, nodes:[{node:'pve-amd', address:'192.168.1.98', state:'ready'}], suggestions:[{node:'pve-amd', address:'192.168.1.98'}, {node:'pve-intel', address:'192.168.1.99'}]});
  assert.deepEqual(rows.map(r => [r.node, r.state]),[['pve-amd','ready'],['pve-intel','not_enrolled']]);
});
test('agentRows / boundary: no Proxmox connection and no nodes', () => {
  assert.deepEqual(agentRows({proxy:true, nodes:[], suggestions:[]}),[]);
  assert.equal(agentRows({proxy:true, nodes:[{node:'x', address:'1.2.3.4'}], suggestions:[]})[0].state,'unreachable');
});
test('agentRows / faal: malformed overview is rejected', () => {
  assert.throws(() => agentRows({proxy:true, nodes:null, suggestions:[]}),TypeError);
});
test('agentStateText / normaal, boundary and faal: every state has text; unknown is never ok', () => {
  assert.equal(agentStateText('ready').level,'ok');
  for (const state of ['outdated','not_installed','hostkey_changed','unreachable','not_enrolled']) assert.notEqual(agentStateText(state).level,'ok');
  assert.equal(agentStateText(undefined).level,'unknown');
  assert.equal(agentStateText('something').level,'unknown');
});
