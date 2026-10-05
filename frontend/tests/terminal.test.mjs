import test from 'node:test';
import assert from 'node:assert/strict';
import {startTerminal} from '../lib/terminal.ts';

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
