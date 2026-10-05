import assert from 'node:assert/strict';
import { test } from 'node:test';
import { firstRoute, getDestinations, href, isActive } from '../lib/navigation.ts';

const modules = [
  {id:'dashboard', enabled:true, title:'Mijn dashboard', view:'empty'},
  {id:'kasm', enabled:true, title:'Kasm', view:'integration', provider:'kasm', pages:[{id:'sessions',title:'Sessies'}]},
];
const menu = [
  {id:'external', label:'Project', url:'https://example.test'},
  {id:'apps', label:'Apps', children:[{id:'kasm',label:'Kasm',route:'kasm'}]},
];

test('getDestinations / normaal: module and subpage keep their title, view and provider', () => {
  const destinations = getDestinations({modules});
  assert.equal(destinations[0].label,'Mijn dashboard');
  assert.equal(destinations[0].view,'empty');
  assert.deepEqual(destinations[2],{id:'kasm/sessions',label:'Sessies',description:undefined,view:'placeholder',provider:'kasm'});
});
test('getDestinations / boundary: zero permitted modules yields no invented pages', () => {
  assert.deepEqual(getDestinations({modules:[]}),[]);
});
test('getDestinations / faal: malformed module input is not accepted', () => {
  assert.throws(() => getDestinations({modules:null}),TypeError);
});
test('firstRoute / normaal: follows a dropdown route after external links', () => {
  assert.equal(firstRoute(menu),'kasm');
});
test('firstRoute / boundary: an empty menu has no default route', () => {
  assert.equal(firstRoute([]),undefined);
});
test('firstRoute / faal: missing route in a malformed item cannot invent navigation', () => {
  assert.equal(firstRoute([{id:'broken',label:'Broken'}]),undefined);
});
test('isActive / normaal: dropdown follows its child route', () => {
  assert.equal(isActive(menu[1],'kasm'),true);
});
test('isActive / boundary: empty dropdown stays inactive', () => {
  assert.equal(isActive({id:'empty',label:'Empty',children:[]},'kasm'),false);
});
test('isActive / faal: matching the dropdown id is not access to its child', () => {
  assert.equal(isActive(menu[1],'apps'),false);
});
test('href / normaal: returns the configured route', () => {
  assert.equal(href({route:'kasm'}),'#kasm');
});
test('href / boundary: nested subpage and external link remain intact', () => {
  assert.equal(href({route:'proxmox/nodes'}),'#proxmox/nodes');
  assert.equal(href(menu[0]),'https://example.test');
});
test('href / faal: missing destinations are rejected', () => {
  assert.throws(() => href({id:'broken'}),TypeError);
});
