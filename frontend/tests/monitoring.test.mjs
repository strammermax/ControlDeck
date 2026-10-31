import assert from 'node:assert/strict';
import { test } from 'node:test';
import { connectionStatus, groupBySource, manualConnectionError, sinceText, summarize } from '../lib/monitoring.ts';

const row = (source, host, ok, checked = 100) => ({ id: `${source}-${host}`, origin: 'sonarr', source, vmid: null, host, port: 80, label: '', ok, checked, since: 50, error: null, ms: null, ip: null, via: null });

test('connectionStatus / normaal: online and broken', () => {
  assert.equal(connectionStatus(row('a', 'x', true)).level, 'ok');
  assert.equal(connectionStatus(row('a', 'x', false)).level, 'error');
});
test('connectionStatus / boundary: never checked or failed check is unknown, never ok', () => {
  assert.equal(connectionStatus(row('a', 'x', true, null)).level, 'unknown');
  assert.equal(connectionStatus(row('a', 'x', null)).level, 'unknown');
});
test('groupBySource / normaal: broken groups first, broken rows first inside a group', () => {
  const groups = groupBySource([row('Sonarr', 'b', true), row('Lidarr', 'q', true), row('Sonarr', 'a', false)]);
  assert.deepEqual(groups.map(g => [g.source, g.down]), [['Sonarr', 1], ['Lidarr', 0]]);
  assert.deepEqual(groups[0].connections.map(c => c.host), ['a', 'b']);
});
test('groupBySource / boundary and faal: empty list, malformed input', () => {
  assert.deepEqual(groupBySource([]), []);
  assert.throws(() => groupBySource(null), TypeError);
});
test('summarize counts every level', () => {
  assert.deepEqual(summarize([row('a', 'x', true), row('a', 'y', false), row('a', 'z', null)]), { total: 3, ok: 1, down: 1, unknown: 1 });
});
test('sinceText / normaal, boundary and faal', () => {
  assert.equal(sinceText(1000, 1030), 'sinds zojuist');
  assert.equal(sinceText(1000, 1000 + 600), 'sinds 10 min');
  assert.equal(sinceText(1000, 1000 + 7200), 'sinds 2 u');
  assert.equal(sinceText(1000, 1000 + 3 * 86400), 'sinds 3 d');
  assert.equal(sinceText(null, 1000), '');
  assert.equal(sinceText(5000, 1000), '');
});
test('manualConnectionError / normaal, boundary and faal', () => {
  const ok = { source: 'Home Assistant', host: '192.168.1.96', port: '6638', vmid: '' };
  assert.equal(manualConnectionError(ok), '');
  assert.equal(manualConnectionError({ ...ok, port: '65535', vmid: '100' }), '');
  assert.match(manualConnectionError({ ...ok, source: ' ' }), /bron/);
  assert.match(manualConnectionError({ ...ok, host: 'a b' }), /host/);
  assert.match(manualConnectionError({ ...ok, port: '0' }), /Poort/);
  assert.match(manualConnectionError({ ...ok, port: '65536' }), /Poort/);
  assert.match(manualConnectionError({ ...ok, vmid: '99' }), /Container/);
});
test('scope / normaal, boundary and faal: private vs public addresses and names', async () => {
  const { scope } = await import('../lib/monitoring.ts');
  for (const host of ['192.168.1.96', '10.0.0.1', '172.31.0.1', '100.64.0.1', 'arrsuite.home', 'qbittorrent', 'printer.local', 'fd00::1', 'localhost']) assert.equal(scope(host), 'intern', host);
  for (const host of ['1.1.1.1', '172.32.0.1', 'api.open-meteo.com', 'Removesky.Vanburik.Info.', '2606:4700::1111']) assert.equal(scope(host), 'internet', host);
});
test('parseRecipients / normaal, boundary and faal', async () => {
  const { parseRecipients } = await import('../lib/monitoring.ts');
  assert.deepEqual(parseRecipients('homelab@vanburik.info, beheer@example.test'), { recipients: ['homelab@vanburik.info', 'beheer@example.test'], invalid: [] });
  assert.deepEqual(parseRecipients(' A@x.nl;\na@X.nl  '), { recipients: ['A@x.nl'], invalid: [] });
  assert.deepEqual(parseRecipients(''), { recipients: [], invalid: [] });
  assert.deepEqual(parseRecipients('geen-adres, x@y'), { recipients: [], invalid: ['geen-adres', 'x@y'] });
});
test('mailSystems / normaal, boundary and faal', async () => {
  const { mailSystems } = await import('../lib/monitoring.ts');
  const mail = (system, level) => ({ uid: 1, from: '', address: '', subject: '', date: null, unread: false, system, level });
  assert.deepEqual(mailSystems([mail('Sonarr', 'ok'), mail('NAS', 'error'), mail('NAS', 'info')]), [{ system: 'NAS', total: 2, errors: 1 }, { system: 'Sonarr', total: 1, errors: 0 }]);
  assert.deepEqual(mailSystems([]), []);
  assert.throws(() => mailSystems(undefined), TypeError);
});
