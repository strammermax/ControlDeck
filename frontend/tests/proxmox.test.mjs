import assert from 'node:assert/strict';
import { test } from 'node:test';
import { cleanAddress, describeTask, duration, filterTasks } from '../lib/proxmox.ts';

const task = (extra) => ({id:'U', node:'pve-amd', user:'root@pam', type:'vzstart', target:'165', targetType:'lxc', targetName:'controldeck', start:100, end:102, status:'ok', message:null, ...extra});
test('describeTask / normaal: container start with name', () => {
  assert.equal(describeTask(task()),'CT 165 (controldeck) – Start');
  assert.equal(describeTask(task({type:'vzdump', target:'200', targetType:'qemu', targetName:'win'})),'VM 200 (win) – Backup');
});
test('describeTask / boundary: no target, removed guest and unknown type', () => {
  assert.equal(describeTask(task({type:'vncshell', target:''})),'Shell');
  assert.equal(describeTask(task({type:'qmstop', target:'999', targetType:null, targetName:null})),'VM 999 – Stop');
  assert.equal(describeTask(task({type:'cephcreateosd', target:'osd.1', targetType:null, targetName:null})),'cephcreateosd osd.1');
});
test('describeTask / faal: untrusted text stays plain text without markup', () => {
  assert.equal(describeTask(task({targetName:'<b>x</b>'})),'CT 165 (<b>x</b>) – Start');
});
test('filterTasks / normaal: node and status filters combine', () => {
  const tasks = [task(), task({id:'B', node:'pve-nas', status:'error'}), task({id:'C', status:'error'})];
  assert.deepEqual(filterTasks(tasks,{node:'pve-amd', status:'error'}).map(t => t.id),['C']);
});
test('filterTasks / boundary: empty filter returns everything; empty list stays empty', () => {
  assert.equal(filterTasks([task()],{node:'', status:''}).length,1);
  assert.deepEqual(filterTasks([],{node:'pve-amd', status:'ok'}),[]);
});
test('filterTasks / faal: malformed input is rejected', () => {
  assert.throws(() => filterTasks(null,{node:'', status:''}),TypeError);
});
test('duration / normaal, boundary and faal', () => {
  assert.equal(duration(100,145,0),'45s');
  assert.equal(duration(0,185,0),'3m 05s');
  assert.equal(duration(0,7440,0),'2u 04m');
  assert.equal(duration(100,null,160),'1m 00s');
  assert.equal(duration(100,50,0),'0s');
});
test('cleanAddress / normaal, boundary and faal', () => {
  assert.equal(cleanAddress(' https://192.168.1.98:8006/# '),'https://192.168.1.98:8006');
  assert.equal(cleanAddress('https://pm.vanburik.info'),'https://pm.vanburik.info');
  assert.equal(cleanAddress(''),'');
});
import { bytes, meter } from '../lib/proxmox.ts';
test('meter / normaal: value becomes bar width with load level', () => {
  assert.deepEqual(meter(42.5),{width:42.5, level:'normal'});
  assert.equal(meter(80).level,'high');
});
test('meter / boundary: 0, 75, 90 and >100 are clamped and classified', () => {
  assert.deepEqual(meter(0),{width:0, level:'normal'});
  assert.equal(meter(75).level,'high');
  assert.equal(meter(90).level,'critical');
  assert.deepEqual(meter(250),{width:100, level:'critical'});
});
test('meter / faal: missing or invalid values are unknown, never healthy', () => {
  for (const value of [null, undefined, NaN, Infinity]) assert.deepEqual(meter(value),{width:0, level:'unknown'});
});
test('bytes / normaal, boundary and faal', () => {
  assert.equal(bytes(64 * 1024 ** 3),'64 GiB');
  assert.equal(bytes(1536),'1.5 KiB');
  assert.equal(bytes(0),'0 B');
  assert.equal(bytes(-1),'—');
  assert.equal(bytes(null),'—');
});
import { diskLevel, healthProblems } from '../lib/proxmox.ts';
test('healthProblems / normaal: problems first, healthy only counted', () => {
  const result = healthProblems([{id:'cpu',status:'ok',reason:null},{id:'remote_mounts',status:'warning',reason:'x'},{id:'lxc_mounts',status:'error',reason:'y'}]);
  assert.deepEqual(result.problems.map(p => p.id),['lxc_mounts','remote_mounts']);
  assert.equal(result.healthy,1);
});
test('healthProblems / boundary: missing or all-healthy categories', () => {
  assert.deepEqual(healthProblems(undefined),{problems:[],healthy:0});
  assert.equal(healthProblems([{id:'cpu',status:'ok',reason:null}]).problems.length,0);
});
test('healthProblems / faal: unknown stays a problem; malformed input is rejected', () => {
  assert.equal(healthProblems([{id:'x',status:'unknown',reason:null}]).problems.length,1);
  assert.throws(() => healthProblems('x'),TypeError);
});
const disk = extra => ({name:'sda',model:null,health:'healthy',smart:'passed',temperature:30,wear:5,reallocated:0,pending:0,standby:false,size:null,...extra});
test('diskLevel / normaal: healthy disk', () => { assert.equal(diskLevel(disk()),'ok'); });
test('diskLevel / boundary: 89 vs 90 % wear and one reallocated sector', () => {
  assert.equal(diskLevel(disk({wear:89})),'ok');
  assert.equal(diskLevel(disk({wear:90})),'warning');
  assert.equal(diskLevel(disk({reallocated:1})),'warning');
});
test('diskLevel / faal: SMART failure or pending sectors are errors; unknown SMART is not healthy', () => {
  assert.equal(diskLevel(disk({smart:'FAILED'})),'error');
  assert.equal(diskLevel(disk({pending:2})),'error');
  assert.equal(diskLevel(disk({smart:'unknown',health:'unknown'})),'unknown');
});
import { monitorGuidance } from '../lib/proxmox.ts';
test('monitorGuidance / normaal: ready needs no steps', () => {
  assert.deepEqual(monitorGuidance('ready'),{label:'Klaar om te koppelen', level:'ok', steps:[]});
});
test('monitorGuidance / boundary: every not-ready state has concrete steps', () => {
  for (const state of ['auth_disabled','untrusted_tls','http_only','absent']) assert.ok(monitorGuidance(state).steps.length > 0, state);
  assert.equal(monitorGuidance('absent').level,'error');
});
test('monitorGuidance / faal: unknown or missing state is never ready', () => {
  assert.equal(monitorGuidance(undefined).level,'unknown');
  assert.equal(monitorGuidance('something').level,'unknown');
});
import { collectUpdates, diskStatus } from '../lib/proxmox.ts';
test('diskStatus / normaal: a readable disk keeps its level', () => {
  assert.equal(diskStatus(disk()),'ok');
});
test('diskStatus / boundary: a sleeping disk without SMART is "standby", not unknown', () => {
  assert.equal(diskStatus(disk({smart:'unknown',health:'unknown',standby:true})),'standby');
  assert.equal(diskStatus(disk({smart:'FAILED',standby:true})),'error');
});
test('diskStatus / faal: an awake disk without SMART stays unknown', () => {
  assert.equal(diskStatus(disk({smart:'unknown',health:'unknown',standby:false})),'unknown');
});
const upd = (id, security, count) => ({id, name:`ct${id}`, count, security, packages:[]});
test('collectUpdates / normaal: security first across all nodes, with totals', () => {
  const result = collectUpdates([{name:'pve-amd', monitorUrl:'https://amd:8008', lxcUpdates:[upd(103,0,4), upd(137,26,50)]}, {name:'pve-intel', lxcUpdates:[upd(105,5,5)]}]);
  assert.deepEqual(result.rows.map(r => r.id),[137,105,103]);
  assert.equal(result.rows[0].monitorUrl,'https://amd:8008');
  assert.equal(result.rows[1].monitorUrl,undefined);
  assert.equal(result.containers,3);
  assert.equal(result.security,31);
  assert.deepEqual(result.missing,[]);
});
test('collectUpdates / boundary: no updates and equal security sorted by count', () => {
  assert.deepEqual(collectUpdates([{name:'a', lxcUpdates:[]}]),{rows:[], containers:0, security:0, missing:[]});
  assert.deepEqual(collectUpdates([{name:'a', lxcUpdates:[upd(1,0,2), upd(2,0,9)]}]).rows.map(r => r.id),[2,1]);
});
test('collectUpdates / faal: unreachable or partial nodes are listed as missing, never as up to date', () => {
  const result = collectUpdates([{name:'pve-intel', overall:'unknown', error:'x'}, {name:'pve-nas', partial:['containers'], lxcUpdates:[]}]);
  assert.deepEqual(result.missing,['pve-intel','pve-nas']);
  assert.throws(() => collectUpdates(null),TypeError);
});
import { UPDATE_LXCS_COMMAND, updatesPerNode } from '../lib/proxmox.ts';
const row = (node, id, security) => ({node, id, name:`ct${id}`, count:1, security, packages:[]});
test('updatesPerNode / normaal: groups containers per node, most security updates first', () => {
  assert.deepEqual(updatesPerNode([row('pve-amd',137,26), row('pve-intel',105,5), row('pve-amd',103,0), row('pve-intel',127,5)]),
    [{node:'pve-amd',containers:2,security:26},{node:'pve-intel',containers:2,security:10}]);
});
test('updatesPerNode / boundary: no rows and missing security counts', () => {
  assert.deepEqual(updatesPerNode([]),[]);
  assert.deepEqual(updatesPerNode([{...row('pve-nas',1,0), security:null}]),[{node:'pve-nas',containers:1,security:0}]);
});
test('updatesPerNode / faal: malformed input is rejected; the command is the official host script', () => {
  assert.throws(() => updatesPerNode(null),TypeError);
  assert.match(UPDATE_LXCS_COMMAND,/^bash -c "\$\(curl -fsSL https:\/\/raw\.githubusercontent\.com\/community-scripts\/ProxmoxVE\/main\/tools\/pve\/update-lxcs\.sh\)"$/);
});
