import assert from 'node:assert/strict';
import { test } from 'node:test';
import { moveItem, orderMenu } from '../lib/navigation.ts';
import { translate } from '../lib/i18n.ts';

const top = [{id:'dashboard',label:'Dashboard'},{id:'proxmox',label:'Proxmox',children:[{id:'n',label:'Nodes',route:'proxmox/nodes'}]},{id:'admin',label:'Admin'}];
test('orderMenu / normaal: personal order moves groups as a unit with their children', () => {
  const result = orderMenu(top,['admin','proxmox','dashboard']);
  assert.deepEqual(result.map(item => item.id),['admin','proxmox','dashboard']);
  assert.equal(result[1].children[0].route,'proxmox/nodes');
});
test('orderMenu / boundary: empty order keeps configuration; unordered items follow ordered ones', () => {
  assert.equal(orderMenu(top,[]),top);
  assert.deepEqual(orderMenu(top,['admin']).map(item => item.id),['admin','dashboard','proxmox']);
});
test('orderMenu / faal + autorisatie: unknown or hidden ids never add menu items', () => {
  assert.deepEqual(orderMenu(top,['secret','admin']).map(item => item.id),['admin','dashboard','proxmox']);
  assert.equal(orderMenu(top.slice(0,2),['admin']).some(item => item.id === 'admin'),false);
  assert.throws(() => orderMenu(null,['admin']),TypeError);
});
test('moveItem / normaal: moves an item without mutating the original', () => {
  const list = ['a','b','c'];
  assert.deepEqual(moveItem(list,2,0),['c','a','b']);
  assert.deepEqual(list,['a','b','c']);
});
test('moveItem / boundary: first, last and single-item positions', () => {
  assert.deepEqual(moveItem(['a','b','c'],0,2),['b','c','a']);
  assert.deepEqual(moveItem(['a'],0,0),['a']);
});
test('moveItem / faal: positions outside the list are rejected', () => {
  assert.throws(() => moveItem(['a','b'],0,2),RangeError);
  assert.throws(() => moveItem(['a','b'],-1,0),RangeError);
  assert.throws(() => moveItem([],0,0),RangeError);
});
test('translate / normaal: English and Dutch texts', () => {
  assert.equal(translate('en','save'),'Save');
  assert.equal(translate('nl','save'),'Opslaan');
});
test('translate / boundary + faal: missing or unsupported language falls back to Dutch', () => {
  assert.equal(translate(undefined,'save'),'Opslaan');
  assert.equal(translate('de','save'),'Opslaan');
});
