import test from 'node:test';
import assert from 'node:assert/strict';
import {workfarmUrl} from '../lib/workfarm.ts';
test('workfarm normaal: light and dark propagate to the embedded page',()=>{
 assert.equal(workfarmUrl('light'),'/workfarm/?theme=light&embedded=1');
 assert.equal(workfarmUrl('dark'),'/workfarm/?theme=dark&embedded=1');
});
test('workfarm boundary: standalone keeps the theme without hiding its header',()=>{
 assert.equal(workfarmUrl('light',false),'/workfarm/?theme=light');
});
test('workfarm faal: arbitrary theme and URL input rejected',()=>{
 for(const theme of ['',null,'system','dark&next=evil'])assert.throws(()=>workfarmUrl(theme));
});
