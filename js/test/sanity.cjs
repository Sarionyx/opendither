// Behavioural checks that don't depend on exact hashes.
'use strict';
const assert = require('assert');
const OD = require('../src/opendither.js');

function flat(w, h, v) {
  const d = new Uint8ClampedArray(w * h * 4);
  for (let i = 0; i < d.length; i += 4) { d[i] = d[i + 1] = d[i + 2] = v; d[i + 3] = 255; }
  return { data: d, width: w, height: h };
}
const mean = (r) => { let s = 0; for (let i = 0; i < r.data.length; i += 4) s += r.data[i]; return s / (r.data.length / 4); };

let n = 0;
function test(name, fn) { fn(); n++; console.log('ok  ', name); }

test('every algorithm outputs only palette colors and keeps mid-gray near 50%', () => {
  for (const a of OD.algorithms) {
    const r = OD.dither(flat(64, 64, 128), { algorithm: a.id });
    for (let i = 0; i < r.data.length; i += 4) assert.ok(r.data[i] === 0 || r.data[i] === 255, a.id);
    if (a.id !== 'threshold') assert.ok(Math.abs(mean(r) - 128) < 20, `${a.id} mean ${mean(r)}`);
  }
});

test('matrices are permutations of (k+0.5)/n²', () => {
  for (const id of ['bayer-2', 'bayer-4', 'bayer-8', 'bayer-16', 'cluster-4', 'halftone-8', 'lines-h', 'lines-v', 'diagonal']) {
    const m = OD.getMatrix(id), seen = new Set();
    for (const t of m.t) seen.add(Math.round(t * m.n * m.n - 0.5));
    assert.strictEqual(seen.size, m.n * m.n, id);
  }
});

test('pixel scale makes square blocks and keeps size', () => {
  const r = OD.dither(flat(10, 7, 100), { algorithm: 'bayer-4', scale: 4 });
  assert.strictEqual(r.width, 10); assert.strictEqual(r.height, 7);
  for (let y = 0; y < 7; y++) for (let x = 0; x < 10; x++) {
    const a = (y * 10 + x) * 4, b = ((y - (y % 4)) * 10 + (x - (x % 4))) * 4;
    assert.strictEqual(r.data[a], r.data[b]);
  }
});

test('adaptive palette has requested size', () => {
  const img = flat(32, 32, 0);
  for (let i = 0; i < img.data.length; i += 4) { img.data[i] = i % 255; img.data[i + 1] = (i / 7) % 255; }
  const r = OD.dither(img, { adaptive: 6, colorMode: 'rgb' });
  assert.strictEqual(r.palette.length, 6);
});

test('palette parsing', () => {
  assert.deepStrictEqual(OD.parseColor('#fa0'), [255, 170, 0]);
  assert.deepStrictEqual(OD.resolvePalette('#000, #fff'), [[0, 0, 0], [255, 255, 255]]);
  assert.strictEqual(OD.resolvePalette('ega-16').length, 16);
});

test('built-in palettes match spec/palettes.json', () => {
  const spec = JSON.parse(require('fs').readFileSync(require('path').join(__dirname, '..', '..', 'spec', 'palettes.json'), 'utf8'));
  assert.deepStrictEqual(OD.palettes, spec);
});

console.log(`${n} sanity tests passed`);
