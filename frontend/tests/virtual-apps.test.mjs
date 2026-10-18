import test from 'node:test';
import assert from 'node:assert/strict';
import {validateOverview, connectLink, virtualAppsRequest, VirtualAppsError} from '../lib/virtual-apps.ts';

const ID = 'a'.repeat(32), PORTAL = 'https://kasm.example.test';
const app = {id: ID, name: 'Chrome', description: '', icon: `${PORTAL}/img/thumbnails/chrome.png`, categories: ['Browser']};
const session = {id: 'd'.repeat(32), appId: ID, name: 'Chrome', status: 'running', started: '', expires: ''};

test('virtual apps normaal: overview and connect link', () => {
  const data = validateOverview({apps: [app], sessions: [session], portal: PORTAL});
  assert.equal(data.apps[0].icon, `${PORTAL}/img/thumbnails/chrome.png`);
  assert.equal(connectLink(`${PORTAL}/#/connect/kasm/${'f'.repeat(32)}/user/token-1`, PORTAL), `${PORTAL}/#/connect/kasm/${'f'.repeat(32)}/user/token-1`);
});

test('virtual apps boundary: empty lists, no icon, dashed ids and session without app', () => {
  assert.deepEqual(validateOverview({apps: [], sessions: [], portal: PORTAL}).apps, []);
  assert.equal(validateOverview({apps: [{...app, icon: null, id: '11111111-2222-3333-4444-555555555555'}], sessions: [{...session, appId: null}], portal: PORTAL}).apps[0].icon, null);
});

test('virtual apps faal: bad ids, insecure icons, foreign or tampered links', () => {
  for (const bad of [{apps: [{...app, id: '../x'}], sessions: [], portal: PORTAL}, {apps: [{...app, icon: 'http://kasm.example.test/a.png'}], sessions: [], portal: PORTAL},
    {apps: [{...app, icon: 'javascript:alert(1)'}], sessions: [], portal: PORTAL}, {apps: [], sessions: [{...session, id: 'x'}], portal: PORTAL}, {apps: [], sessions: [], portal: 'http://kasm.example.test'}, null]) {
    assert.throws(() => validateOverview(bad));
  }
  for (const link of ['https://evil.example.test/#/connect/kasm/a/b/c', `${PORTAL}/?x=1#/connect/kasm/a/b/c`, `${PORTAL}/#/admin`, 'javascript:alert(1)']) assert.throws(() => connectLink(link, PORTAL), link);
});

test('virtual apps request faal/autorisatie: CSRF on writes, flags and refused routes', async () => {
  const original = globalThis.fetch, calls = [];
  try {
    globalThis.fetch = async (url, init) => { calls.push([url, init]); return {ok: false, status: 403, json: async () => ({error: 'Er is geen Kasm-account aan jouw profiel gekoppeld.', notLinked: true})}; };
    await assert.rejects(() => virtualAppsRequest(''), error => error instanceof VirtualAppsError && error.notLinked && !error.notConfigured);
    await assert.rejects(() => virtualAppsRequest('/../admin'), /Ongeldige/);
    assert.equal(calls.length, 1);
    globalThis.fetch = async (url, init) => { calls.push([url, init]); return {ok: true, status: 200, json: async () => ({url: 'x'})}; };
    await virtualAppsRequest(`/${ID}/start`, 'token', 'POST');
    assert.equal(calls.at(-1)[0], `/api/virtual-apps/${ID}/start`);
    assert.equal(calls.at(-1)[1].headers['X-CSRF-Token'], 'token');
    assert.equal(calls.at(-1)[1].body, '{}', 'the browser never sends a user or image choice in the body');
    globalThis.fetch = async () => { throw new TypeError('network'); };
    await assert.rejects(() => virtualAppsRequest(''), /niet bereikbaar/);
  } finally { globalThis.fetch = original; }
});
