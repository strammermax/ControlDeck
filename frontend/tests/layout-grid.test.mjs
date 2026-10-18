import test from 'node:test';
import assert from 'node:assert/strict';
import {cellsOverlap, placeCell, firstFreeCell, resizedCell, pointerCell, mergeLayout, layoutOrder, layoutRows} from '../lib/layout-grid.ts';
import {groupCells, withGroupCells, pageLayoutRequest} from '../lib/page-layouts.ts';
import {bookmarkLayout, orderedLinks, groupBookmarks, personalGroups, moveBookmark} from '../lib/bookmark-layout.ts';

const shared = () => groupBookmarks([
  {id: 1, name: 'Plex', url: 'https://plex.example.test', collection: 'Media', description: '', tags: []},
  {id: 2, name: 'Jellyfin', url: 'https://jf.example.test', collection: 'Media', description: '', tags: []},
  {id: 3, name: 'Proxmox', url: 'https://pve.example.test', collection: 'Infra', description: '', tags: []},
]);

test('bookmark move normaal: a link dragged to another group shows there, personally', () => {
  const cells = bookmarkLayout(shared(), []);
  const moved = moveBookmark(cells, '1', 'Infra', {x: 0, y: 0});
  assert.deepEqual(moved.find(cell => cell.id === '1'), {id: '1', group: 'Infra', width: 2, height: 1, x: 0, y: 1}, 'wanted spot taken: first free place');
  const groups = personalGroups(shared(), moved);
  assert.deepEqual(groups.map(group => [group.name, group.links.map(link => link.id).sort()]), [['Media', [2]], ['Infra', [1, 3]]]);
  assert.equal(shared()[0].links.length, 2, 'the shared collection is unchanged');
  const merged = bookmarkLayout(shared(), moved);
  assert.equal(merged.find(cell => cell.id === '1').group, 'Infra');
});

test('bookmark move boundary: free wanted spot, emptied group and clamped size', () => {
  const cells = bookmarkLayout(shared(), []);
  const once = moveBookmark(cells, '3', 'Media', {x: 1, y: 5});
  assert.deepEqual(once.find(cell => cell.id === '3'), {id: '3', group: 'Media', width: 2, height: 1, x: 0, y: 5}, 'x clamped so a 2-wide tile fits');
  assert.deepEqual(personalGroups(shared(), once).map(group => group.links.length), [3, 0], 'empty group stays as a drop target');
  const wide = moveBookmark([{id: '1', group: 'Media', x: 0, y: 0, width: 2, height: 4}], '1', 'Infra');
  assert.deepEqual(wide[0], {id: '1', group: 'Infra', width: 2, height: 4, x: 0, y: 0});
});

test('bookmark move faal: unknown link, unknown group and stale saved groups', () => {
  const cells = bookmarkLayout(shared(), []);
  assert.throws(() => moveBookmark(cells, '99', 'Infra'), /Onbekende bookmark/);
  assert.throws(() => moveBookmark(cells, '1', ''), /Onbekende groep/);
  const stale = [{id: '1', group: 'Verwijderde groep', x: 0, y: 0, width: 2, height: 1}];
  assert.deepEqual(personalGroups(shared(), stale)[0].links.map(link => link.id), [1, 2], 'a group that no longer exists falls back to the shared group');
  assert.deepEqual(personalGroups(shared(), null).map(group => group.links.length), [2, 1]);
});
import {proxmoxPageCells} from '../lib/proxmox-layout.ts';
import {showEditControls, storedEditMode} from '../lib/edit-mode.ts';

test('edit mode normaal/boundary/faal: user mode hides controls, an open draft keeps them, only true enables', () => {
  assert.equal(showEditControls(true, false), true);
  assert.equal(showEditControls(false, false), false);
  assert.equal(showEditControls(false, true), true, 'switching to user mode never strands an unsaved draft');
  assert.equal(storedEditMode({editMode: true}), true);
  for (const value of [{}, null, undefined, {editMode: 'true'}, {editMode: 1}, 'editMode']) assert.equal(storedEditMode(value), false);
  assert.equal(showEditControls('true', false), false);
});

const bounds = {columns: 12, maxHeight: 6, maxRows: 20};
const a = {id: 'a', x: 0, y: 0, width: 4, height: 2};
const b = {id: 'b', x: 4, y: 0, width: 4, height: 1};

test('layout grid normaal: move, resize and find free space without overlap', () => {
  const moved = placeCell([a, b], {...b, x: 8, y: 1}, bounds);
  assert.deepEqual(moved.find(cell => cell.id === 'b'), {id: 'b', x: 8, y: 1, width: 4, height: 1});
  assert.equal(placeCell([a], {...a, width: 6, height: 3}, bounds)[0].width, 6);
  assert.deepEqual(firstFreeCell([a, b], 4, 1, bounds), {x: 8, y: 0});
  assert.deepEqual(layoutOrder([{...b, y: 3}, a, {id: 'c', x: 6, y: 0, width: 1, height: 1}]), ['a', 'c', 'b']);
  assert.equal(layoutRows([a, b]), 2);
});

test('layout grid boundary: edges, clamped resize and pointer mapping', () => {
  assert.equal(placeCell([], {id: 'edge', x: 11, y: 19, width: 1, height: 1}, bounds).length, 1);
  assert.equal(placeCell([], {id: 'full', x: 0, y: 14, width: 12, height: 6}, bounds)[0].height, 6);
  assert.deepEqual(resizedCell({...a, x: 10}, 9, 99, bounds), {...a, x: 10, width: 2, height: 6});
  assert.deepEqual(resizedCell(a, 0, -3, bounds), {...a, width: 1, height: 1});
  const rect = {left: 0, top: 0, width: 1188};
  assert.deepEqual(pointerCell(rect, 5000, 5000, a, bounds, 84, 12), {x: 8, y: 18});
  assert.deepEqual(pointerCell(rect, -50, -50, a, bounds, 84, 12), {x: 0, y: 0});
  assert.deepEqual(pointerCell(rect, 450, 90, a, bounds, 84, 12, {x: 1, y: 0}), {x: 3, y: 1});
  assert.ok(!cellsOverlap(a, {id: 'touching', x: 4, y: 0, width: 1, height: 1}));
  assert.equal(layoutRows([], 2), 2);
});

test('layout grid faal: refuse collisions, out-of-grid cells and a full grid', () => {
  assert.throws(() => placeCell([a, b], {...b, x: 2}, bounds), /bezet/);
  for (const bad of [{...a, x: -1}, {...a, x: 9}, {...a, height: 7}, {...a, y: 19}, {...a, width: 0}, {...a, x: 1.5}, {...a, id: ''}]) {
    assert.throws(() => placeCell([], bad, bounds), /past niet/);
  }
  assert.throws(() => placeCell([], a, {columns: 0, maxHeight: 1, maxRows: 1}), /past niet/);
  assert.throws(() => firstFreeCell([{id: 'all', x: 0, y: 0, width: 12, height: 6}], 1, 1, {columns: 12, maxHeight: 6, maxRows: 6}), /vol/);
  assert.throws(() => firstFreeCell([], 13, 1, bounds), /Ongeldige/);
});

test('merge layout normaal/boundary/faal: keep saved cells, add new items, drop stale and colliding ones', () => {
  const size = () => ({width: 4, height: 1});
  const merged = mergeLayout(['a', 'b', 'new'], [{...a, x: 8}, {...b, x: 0}, {id: 'gone', x: 0, y: 5, width: 1, height: 1}], size, bounds);
  assert.deepEqual(merged.map(cell => cell.id), ['a', 'b', 'new']);
  assert.equal(merged[0].x, 8);
  assert.deepEqual(merged[2], {id: 'new', x: 4, y: 0, width: 4, height: 1});
  assert.deepEqual(mergeLayout([], [a], size, bounds), []);
  assert.deepEqual(mergeLayout(['x'], null, () => ({width: 99, height: 99}), bounds), [{id: 'x', x: 0, y: 0, width: 12, height: 6}]);
  const repaired = mergeLayout(['a', 'b'], [a, {...b, x: 0}, {...a, x: 8}], size, bounds);
  assert.equal(repaired.filter(cell => cell.id === 'a').length, 1);
  assert.ok(!cellsOverlap(repaired[0], repaired[1]), 'a colliding saved cell is re-flowed instead of overlapping');
});

test('page layout cells normaal/boundary: groups are separate grids', () => {
  const cells = [{...a, group: 'Media'}, {...a, group: 'Infra'}];
  assert.deepEqual(groupCells(cells, 'Media'), [a]);
  assert.deepEqual(groupCells(cells, 'Leeg'), []);
  assert.deepEqual(withGroupCells(cells, 'Media', [b]).map(cell => `${cell.group}:${cell.id}`), ['Infra:a', 'Media:b']);
});

test('page layout request faal and autorisatie: unknown pages never reach the network; server errors surface', async () => {
  const original = globalThis.fetch;
  const calls = [];
  try {
    globalThis.fetch = async (url, init) => { calls.push([url, init]); return {ok: false, json: async () => ({error: 'Geen toegang tot deze pagina.'})}; };
    await assert.rejects(() => pageLayoutRequest('admin'), /Onbekende/);
    assert.equal(calls.length, 0);
    await assert.rejects(() => pageLayoutRequest('proxmox'), /Geen toegang/);
    globalThis.fetch = async (url, init) => { calls.push([url, init]); return {ok: true, json: async () => ({cells: [{...a, group: 'main'}]})}; };
    assert.equal((await pageLayoutRequest('bookmarks', 'token', 'PUT', [{...a, group: 'main'}])).length, 1);
    const [url, init] = calls.at(-1);
    assert.equal(url, '/api/layouts/bookmarks');
    assert.equal(init.headers['X-CSRF-Token'], 'token');
    assert.equal(JSON.parse(init.body).cells[0].id, 'a');
  } finally { globalThis.fetch = original; }
});

test('bookmark layout normaal/boundary/faal: per-group cells, reading order and stale links', () => {
  const links = [
    {id: 1, name: 'Plex', url: 'https://plex.example.test', collection: 'Media', description: '', tags: []},
    {id: 2, name: 'Jellyfin', url: 'https://jf.example.test', collection: 'Media', description: '', tags: []},
    {id: 3, name: 'Proxmox', url: 'https://pve.example.test', collection: 'Infra', description: '', tags: []},
  ];
  const groups = groupBookmarks(links);
  const fresh = bookmarkLayout(groups, []);
  assert.deepEqual(fresh.map(cell => [cell.group, cell.id, cell.x, cell.y, cell.width]), [['Media', '1', 0, 0, 2], ['Media', '2', 0, 1, 2], ['Infra', '3', 0, 0, 2]]);
  const saved = [{group: 'Media', id: '2', x: 0, y: 0, width: 1, height: 2}, {group: 'Media', id: '99', x: 1, y: 0, width: 1, height: 1}];
  const merged = bookmarkLayout(groups, saved);
  assert.deepEqual(merged.find(cell => cell.id === '2'), {group: 'Media', id: '2', x: 0, y: 0, width: 1, height: 2});
  assert.ok(!merged.some(cell => cell.id === '99'), 'removed links do not keep a cell');
  assert.deepEqual(orderedLinks(groups[0], merged).map(link => link.id), [2, 1]);
  assert.deepEqual(bookmarkLayout([], saved), []);
});

test('proxmox page layout normaal/boundary: defaults, saved positions and hidden widgets', () => {
  const fresh = proxmoxPageCells(['health', 'guests', 'nodes-cpu', 'tasks'], []);
  assert.deepEqual(fresh.map(cell => [cell.id, cell.x, cell.y, cell.width, cell.height]), [['health', 0, 0, 12, 4], ['guests', 0, 4, 6, 4], ['nodes-cpu', 6, 4, 6, 3], ['tasks', 0, 8, 12, 6]]);
  const saved = proxmoxPageCells(['health', 'tasks'], [{group: 'main', id: 'tasks', x: 0, y: 0, width: 12, height: 6}, {group: 'other', id: 'health', x: 0, y: 0, width: 1, height: 1}]);
  assert.deepEqual(saved.map(cell => [cell.id, cell.y]), [['tasks', 0], ['health', 6]]);
  assert.deepEqual(proxmoxPageCells(['custom'], []), [{id: 'custom', x: 0, y: 0, width: 6, height: 3, group: 'main'}]);
});
