import assert from 'node:assert/strict';
import { test } from 'node:test';
import { rootComponentsNotice } from '../lib/root-components.ts';

const command = 'sudo -u llmuser git -C /home/llmuser/controldeck-bootstrap pull && bash /home/llmuser/controldeck-bootstrap/scripts/install-wizard.sh';
test('rootComponentsNotice / normaal: lists outdated parts with the exact host command', () => {
  assert.deepEqual(rootComponentsNotice({issues:['installatieworker','agent-proxy'], command, checkout:'/home/llmuser/controldeck-bootstrap', proxy:{available:true, version:0, outdated:true}}),
    {title:'Root-onderdelen bijwerken', parts:'installatieworker, agent-proxy', command});
});
test('rootComponentsNotice / boundary: nothing outdated or no status gives no banner', () => {
  assert.equal(rootComponentsNotice({issues:[], command, checkout:null, proxy:{available:true, version:1, outdated:false}}),null);
  assert.equal(rootComponentsNotice(undefined),null);
});
test('rootComponentsNotice / faal: malformed status is rejected', () => {
  assert.throws(() => rootComponentsNotice({issues:'x', command}),TypeError);
});
