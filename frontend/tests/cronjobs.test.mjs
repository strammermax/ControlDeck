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
import { runStatus, suggestJobId, summarizeRuns } from '../lib/cronjobs.ts';
test('runStatus / normaal, boundary and faal', () => {
  assert.deepEqual(runStatus({status:'succeeded'}),{label:'✓ OK', level:'ok'});
  assert.equal(runStatus({status:'failed', exitCode:3}).label,'✗ Fout (exit 3)');
  assert.equal(runStatus({status:'failed', exitCode:0}).label,'✗ Fout (exit 0)');
  assert.equal(runStatus({status:'started'}).level,'unknown');
  assert.equal(runStatus({status:'weird'}).level,'unknown');
});
test('summarizeRuns / normaal, boundary and faal', () => {
  const runs = [{status:'succeeded'},{status:'failed'},{status:'failed'},{status:'running'},{status:'started'}];
  assert.deepEqual(summarizeRuns(runs),{total:5, ok:1, failed:2, running:1, started:1});
  assert.deepEqual(summarizeRuns([]),{total:0, ok:0, failed:0, running:0, started:0});
  assert.throws(() => summarizeRuns(null),TypeError);
});
test('suggestJobId / normaal, boundary and faal', () => {
  assert.equal(suggestJobId('/usr/bin/vzdump --all'),'vzdump');
  assert.equal(suggestJobId('cd / && run-parts --report /etc/cron.hourly'),'cd');
  assert.equal(suggestJobId(''),'overgenomen-job');
  assert.equal(suggestJobId('/opt/My_Script.SH'),'my-script-sh');
});
