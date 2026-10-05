import assert from 'node:assert/strict';
import { test } from 'node:test';
import { releaseNotesUrl } from '../lib/release.ts';

const repo = 'https://github.com/strammermax/ControlDeck';
test('releaseNotesUrl / normaal: a CI build links to its own release', () => {
  assert.equal(releaseNotesUrl(repo,'2026.10.05.31'),'https://github.com/strammermax/ControlDeck/releases/tag/v2026.10.05.31');
});
test('releaseNotesUrl / boundary: semver links to its tag; development or unknown versions to the release list', () => {
  assert.equal(releaseNotesUrl(repo,'0.4.0'),'https://github.com/strammermax/ControlDeck/releases/tag/v0.4.0');
  for (const version of ['development', undefined, '', '0.4', '2026.10.05']) assert.equal(releaseNotesUrl(repo+'/',version),'https://github.com/strammermax/ControlDeck/releases');
});
test('releaseNotesUrl / faal: non-GitHub or unsafe repository URLs give no link', () => {
  for (const url of ['http://github.com/a/b','https://evil.example/a/b','javascript:alert(1)','not a url','https://github.com/a','https://github.com/a/b/c']) assert.equal(releaseNotesUrl(url,'2026.10.05.31'),null);
});
