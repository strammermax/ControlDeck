import test from 'node:test';
import assert from 'node:assert/strict';
import {filesPath, joinPath, parentPath, breadcrumbs, formatSize, uploadPlan, downloadUrl, filesRequest, FilesRequestError, MAX_UPLOAD} from '../lib/files.ts';

test('files paths normaal: normalise, join, parent and breadcrumbs', () => {
  assert.equal(filesPath('/Docs//2026/'), 'Docs/2026');
  assert.equal(joinPath('Docs', 'factuur oktober.pdf'), 'Docs/factuur oktober.pdf');
  assert.equal(parentPath('Docs/2026/a.pdf'), 'Docs/2026');
  assert.deepEqual(breadcrumbs('Docs/2026'), [{name: 'Bestanden', path: ''}, {name: 'Docs', path: 'Docs'}, {name: '2026', path: 'Docs/2026'}]);
  assert.equal(downloadUrl('Docs/a b.pdf'), '/api/files/download?path=Docs%2Fa%20b.pdf');
});

test('files paths boundary: root, unicode and limits', () => {
  assert.equal(filesPath(''), '');
  assert.equal(joinPath('', 'a'), 'a');
  assert.equal(parentPath('a'), '');
  assert.deepEqual(breadcrumbs(''), [{name: 'Bestanden', path: ''}]);
  assert.equal(filesPath('日本/é/' + 'x'.repeat(255)).length, 260);
  assert.equal(formatSize(0), '0 B');
  assert.equal(formatSize(1536), '1,5 KB');
  assert.equal(formatSize(10 * 1024 ** 3), '10 GB');
  assert.equal(formatSize(null), '');
});

test('files paths faal: traversal, control characters and names with slashes', () => {
  for (const bad of ['..', 'a/../b', './a', 'a\\b', 'a\nb', 'x'.repeat(1025), 'a/' + 'y'.repeat(256)]) assert.throws(() => filesPath(bad), /Ongeldig/);
  assert.throws(() => joinPath('Docs', 'a/b'), /schuine/);
  assert.throws(() => joinPath('Docs', ''), /schuine/);
  assert.throws(() => downloadUrl('../etc/passwd'), /Ongeldig/);
});

test('upload plan normaal/boundary/faal: chunks cover the file exactly', () => {
  assert.deepEqual(uploadPlan(10, 4), [{index: 1, start: 0, end: 4}, {index: 2, start: 4, end: 8}, {index: 3, start: 8, end: 10}]);
  assert.deepEqual(uploadPlan(8, 4).map(part => part.end), [4, 8], 'exact multiple has no empty last chunk');
  assert.deepEqual(uploadPlan(0, 4), []);
  assert.equal(uploadPlan(MAX_UPLOAD, 32 * 1024 * 1024).length, 320);
  assert.throws(() => uploadPlan(MAX_UPLOAD + 1, 4), /10 GB/);
  assert.throws(() => uploadPlan(-1, 4), /10 GB/);
  assert.throws(() => uploadPlan(10, 0), /deelgrootte/);
});

test('files request faal/autorisatie: CSRF on writes, relink flag and refused routes', async () => {
  const original = globalThis.fetch;
  const calls = [];
  try {
    globalThis.fetch = async (url, init) => { calls.push([url, init]); return {ok: false, status: 409, json: async () => ({error: 'Koppel eerst', relink: true})}; };
    await assert.rejects(() => filesRequest('/list'), error => error instanceof FilesRequestError && error.relink && error.status === 409);
    await assert.rejects(() => filesRequest('https://evil.test'), /Ongeldige/);
    // Regression 2026-10-17: an HTML error page (413 from the server, or Cloudflare) showed only
    // "Files is niet beschikbaar."; the status is now part of the message.
    globalThis.fetch = async (url, init) => { calls.push([url, init]); return {ok: false, status: 413, json: async () => { throw new SyntaxError('html'); }}; };
    await assert.rejects(() => filesRequest('/upload?path=a'), /status 413/);
    calls.pop();
    assert.equal(calls.length, 1);
    globalThis.fetch = async (url, init) => { calls.push([url, init]); return {ok: true, status: 201, json: async () => ({ok: true})}; };
    await filesRequest('/folder', 'token', 'POST', {path: 'Nieuw'});
    assert.equal(calls.at(-1)[1].headers['X-CSRF-Token'], 'token');
    assert.equal(calls.at(-1)[1].body, '{"path":"Nieuw"}');
    const blob = new Blob(['x']);
    await filesRequest('/upload?path=a', 'token', 'PUT', blob);
    assert.equal(calls.at(-1)[1].body, blob, 'binary bodies are sent as-is');
    assert.equal(calls.at(-1)[1].headers['Content-Type'], undefined);
  } finally { globalThis.fetch = original; }
});
