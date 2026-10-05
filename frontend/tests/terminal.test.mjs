import test from 'node:test';
import assert from 'node:assert/strict';
import {startTerminal, syncTerminalTheme} from '../lib/terminal.ts';

test('terminal normaal: uses protected endpoint and CSRF token', async () => {
  const previous = globalThis.fetch;
  try {
    globalThis.fetch = async (url, options) => {
      assert.equal(url, '/api/termix/session');
      assert.equal(options.method, 'POST');
      assert.equal(options.headers['X-CSRF-Token'], 'csrf');
      return {ok:true,json:async()=>({ready:true})};
    };
    assert.equal(await startTerminal('csrf'), true);
  } finally {globalThis.fetch=previous;}
});
test('terminal boundary: abort signal propagates and unready session is rejected', async () => {
  const previous=globalThis.fetch;
  try {
    const signal=new AbortController().signal;
    globalThis.fetch=async (_,options)=>{assert.equal(options.signal,signal);return {ok:true,json:async()=>({ready:false})};};
    await assert.rejects(startTerminal('csrf',signal), /Invalid/);
  } finally {globalThis.fetch=previous;}
});
test('terminal faal: unavailable service and malformed session fail closed', async () => {
  const previous=globalThis.fetch;
  try {
    globalThis.fetch=async()=>({ok:false});
    await assert.rejects(startTerminal('csrf'), /unavailable/);
    globalThis.fetch=async()=>({ok:true,json:async()=>({ready:'yes'})});
    await assert.rejects(startTerminal('csrf'), /Invalid/);
  } finally {globalThis.fetch=previous;}
});

function themeWindow(initial = ['dark']) {
  const classes = new Set(initial);
  const storage = new Map();
  return {classes, storage, document:{documentElement:{classList:{contains:name=>classes.has(name),remove:name=>classes.delete(name),add:name=>classes.add(name)}}},localStorage:{setItem:(key,value)=>storage.set(key,value)}};
}
test('terminal theme normaal: switches dark to light and persists Termix preference', () => {
  const target=themeWindow();
  assert.equal(syncTerminalTheme(target,'light'),true);
  assert.deepEqual([...target.classes],['light']);
  assert.equal(target.storage.get('vite-ui-theme'),'light');
  assert.equal(syncTerminalTheme(target,'dark'),true);
  assert.deepEqual([...target.classes],['dark']);
});
test('terminal theme boundary: repeated updates preserve other classes and work without storage', () => {
  const target=themeWindow(['nord','layout']);
  target.localStorage.setItem=()=>{throw new Error('Storage denied');};
  assert.equal(syncTerminalTheme(target,'light'),true);
  assert.equal(syncTerminalTheme(target,'light'),true);
  assert.deepEqual([...target.classes],['layout','light']);
});
test('terminal theme faal: absent, cross-origin and invalid targets fail without mutation', () => {
  assert.equal(syncTerminalTheme(null,'light'),false);
  const target=themeWindow();
  assert.equal(syncTerminalTheme(target,'invalid'),false);
  assert.deepEqual([...target.classes],['dark']);
  assert.equal(syncTerminalTheme({get document(){throw new Error('Cross origin');}},'light'),false);
});
