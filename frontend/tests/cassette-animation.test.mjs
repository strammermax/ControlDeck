import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
const html = readFileSync(new URL('../../docs/cassette-animatie.html', import.meta.url), 'utf8');
function setup(reduced = false) {
  const draws = [];
  const ctx = new Proxy({}, { get: (_, key) => (...args) => draws.push([key, ...args]), set: (_, key, value) => { draws.push(['set', key, value]); return true; } });
  const button = { disabled: true, setAttribute(k,v) { this[k]=v; }, addEventListener(_,f) { this.click=f; } };
  const status = {};
  let photo, callback, cancelled = false;
  const sandbox = { document: { querySelector: s => s==='canvas' ? { getContext:()=>ctx } : s==='button' ? button : status }, Image: class { constructor(){ photo=this; } }, matchMedia:()=>({matches:reduced}), requestAnimationFrame:f=>{ callback=f; return 1; }, cancelAnimationFrame:()=>{cancelled=true;} };
  vm.runInNewContext(html.match(/<script>([\s\S]*?)<\/script>/)[1], sandbox);
  return { button,status,photo,draws,step:t=>callback(t),cancelled:()=>cancelled };
}
test('normal: supplied photo animates both reels and pause stops playback',()=>{
  const s=setup(); assert.ok(s.photo.src.startsWith('data:image/png;base64,')); s.photo.onload();
  assert.equal(s.button['aria-pressed'],'true'); s.step(0);s.step(50);
  assert.ok(s.draws.some(([k,a])=>k==='rotate'&&a<0));
  s.button.click();assert.equal(s.button['aria-pressed'],'false');assert.equal(s.cancelled(),true);
});
test('boundary: reduced motion waits for explicit play, long frame gaps stay bounded',()=>{
  const s=setup(true);s.photo.onload();assert.ok(s.button.textContent.endsWith(' Afspelen'));s.button.click();s.step(0);s.step(1000000);
  const angles=s.draws.filter(([k])=>k==='rotate').map(([,a])=>a);assert.ok(Math.max(...angles.map(Math.abs))<0.14);
});
test('failure: image loading failure disables playback with an explanation',()=>{
  const s=setup();s.photo.onerror();assert.equal(s.button.disabled,true);assert.match(s.status.textContent,/niet worden geladen/);
});

// Regression: clockwise rotation and almost invisible transport made the tape appear stationary.
test('regression: reels turn left and both tape packs and transport move between frames',()=>{
  const s=setup();s.photo.onload();s.step(0);s.draws.length=0;s.step(50);
  const rotations=s.draws.filter(([k])=>k==='rotate').map(([,a])=>a);
  assert.equal(rotations.length,6);assert.ok(rotations.every(a=>a<0));
  assert.ok(s.draws.some(([k,x,y,w,h])=>k==='fillRect'&&y===574&&w===1&&h===3&&x!==146));
  assert.ok(s.draws.some(([k,x,y,r])=>k==='arc'&&x===295&&r>190));
  s.button.click();s.draws.length=0;s.step(100);assert.equal(s.draws.length,0);
});

// Regression: rectangular photo backdrop and dashed overlay spoiled the realistic cassette view.
test('presentation: black surround, clipped photo and continuous tape without dashed overlay',()=>{
  const s=setup();s.photo.onload();
  assert.match(html,/background:#000/);
  assert.ok(s.draws.some(([k,x,y,w,h])=>k==='roundRect'&&x===23&&y===42&&w===940&&h===596));
  assert.equal(s.draws.some(([k])=>k==='setLineDash'),false);
});

