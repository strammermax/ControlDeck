import assert from 'node:assert/strict';
import { test } from 'node:test';
import { buildCron, describeCron, isMissed, nextRuns, parseCron, pickerFor, previousRun } from '../lib/cron.ts';

const at = (text) => new Date(text);
const hm = (date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;

test('parseCron / normaal, boundary and faal', () => {
  assert.ok(parseCron('30 2 * * *'));
  assert.ok(parseCron('*/15 8-18 * * mon-fri'));
  assert.ok(parseCron('@weekly'));
  assert.ok(parseCron('59 23 31 12 7'));
  for (const bad of ['60 * * * *', '* 24 * * *', '* * 0 * *', '* * * 13 *', '* * * * 8', '* * * *', '*/0 * * * *', 'a b c d e', '', null]) assert.equal(parseCron(bad), null, String(bad));
});

test('describeCron / normaal: common schedules in plain Dutch', () => {
  assert.equal(describeCron('30 2 * * *'), 'Elke dag om 02:30');
  assert.equal(describeCron('*/15 * * * *'), 'Elke 15 minuten');
  assert.equal(describeCron('5 * * * *'), 'Elk uur op minuut 5');
  assert.equal(describeCron('0 3 * * 0'), 'Elke zondag om 03:00');
  assert.equal(describeCron('0 7 * * 1-5'), 'Elke werkdag om 07:00');
  assert.equal(describeCron('0 4 1 * *'), 'Op dag 1 van elke maand om 04:00');
});
test('describeCron / boundary + faal: special strings, raw fallback, invalid', () => {
  assert.equal(describeCron('@daily'), 'Elke dag om 00:00');
  assert.equal(describeCron('0 0 1,15 1 *'), 'Volgens cronschema 0 0 1,15 1 *');
  assert.equal(describeCron('99 * * * *'), 'Ongeldig schema');
});

test('nextRuns / normaal: daily and weekly', () => {
  assert.deepEqual(nextRuns('30 2 * * *', at('2026-10-05T12:00:00'), 2).map(hm), ['2026-10-06 02:30', '2026-10-07 02:30']);
  assert.deepEqual(nextRuns('0 3 * * 0', at('2026-10-05T12:00:00'), 1).map(hm), ['2026-10-11 03:00']);
});
test('nextRuns / boundary: month end, leap day and dom-or-dow semantics', () => {
  assert.deepEqual(nextRuns('0 0 31 * *', at('2026-10-31T00:00:00'), 2).map(hm), ['2026-12-31 00:00', '2027-01-31 00:00']);
  // Regression: the search was limited to one year, so a 29 February schedule had no next run.
  assert.deepEqual(nextRuns('0 12 29 2 *', at('2026-10-05T00:00:00'), 1).map(hm), ['2028-02-29 12:00']);
  assert.equal(hm(previousRun('0 12 29 2 *', at('2026-10-05T00:00:00'))), '2024-02-29 12:00');
  // day 1 OR monday
  assert.deepEqual(nextRuns('0 9 1 * 1', at('2026-10-05T10:00:00'), 2).map(hm), ['2026-10-12 09:00', '2026-10-19 09:00']);
});
test('nextRuns / faal: invalid schedules give no runs', () => {
  assert.deepEqual(nextRuns('nope', new Date(), 3), []);
});

test('previousRun / normaal, boundary and faal', () => {
  assert.equal(hm(previousRun('30 2 * * *', at('2026-10-05T12:00:00'))), '2026-10-05 02:30');
  assert.equal(hm(previousRun('30 2 * * *', at('2026-10-05T02:30:00'))), '2026-10-05 02:30');
  assert.equal(previousRun('bad', new Date()), null);
});

test('isMissed / normaal, boundary and faal', () => {
  const now = at('2026-10-05T12:00:00').getTime() / 1000;
  const due = at('2026-10-05T02:30:00').getTime() / 1000;
  const created = due - 86400;
  assert.equal(isMissed('30 2 * * *', true, created, due + 2, now), false);   // ran on time
  assert.equal(isMissed('30 2 * * *', true, created, due - 86400, now), true); // last run was yesterday
  assert.equal(isMissed('30 2 * * *', true, created, null, now), true);       // never ran although due
  assert.equal(isMissed('30 2 * * *', true, due + 60, null, now), false);     // created after the due time
  assert.equal(isMissed('30 2 * * *', false, created, null, now), false);     // paused jobs are never missed
  assert.equal(isMissed('bad', true, created, null, now), false);
});

test('buildCron and pickerFor / normaal: picker round-trips', () => {
  for (const picker of [{mode:'minutes', every:15}, {mode:'hourly', minute:5}, {mode:'daily', time:'02:30'}, {mode:'weekly', days:[1,3], time:'07:00'}, {mode:'monthly', day:1, time:'04:00'}]) {
    assert.deepEqual(pickerFor(buildCron(picker)), picker);
  }
});
test('buildCron / boundary: one minute, sunday, day 28', () => {
  assert.equal(buildCron({mode:'minutes', every:1}), '* * * * *');
  assert.equal(buildCron({mode:'weekly', days:[0], time:'00:00'}), '0 0 * * 0');
  assert.equal(buildCron({mode:'monthly', day:28, time:'23:59'}), '59 23 28 * *');
  assert.deepEqual(pickerFor('0 0 1,15 1 *'), {mode:'advanced', expression:'0 0 1,15 1 *'});
});
test('buildCron / faal: incomplete or invalid input gives null', () => {
  for (const picker of [{mode:'minutes', every:0}, {mode:'daily', time:'24:00'}, {mode:'daily', time:'2'}, {mode:'weekly', days:[], time:'07:00'}, {mode:'monthly', day:31, time:'01:00'}, {mode:'advanced', expression:'0 0 * *'}]) {
    assert.equal(buildCron(picker), null, JSON.stringify(picker));
  }
});
