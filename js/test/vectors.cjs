// Generates / checks spec/test-vectors.json.
//   node test/vectors.cjs           -> check
//   node test/vectors.cjs --write   -> regenerate (only when the spec intentionally changes)
'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const OD = require('../src/opendither.js');

const VECTORS = path.join(__dirname, '..', '..', 'spec', 'test-vectors.json');

function testImage(w, h) {
  const data = new Uint8ClampedArray(w * h * 4);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = (y * w + x) * 4;
      data[i] = Math.floor((x * 255) / (w - 1));
      data[i + 1] = Math.floor((y * 255) / (h - 1));
      data[i + 2] = (x * x + 3 * x * y) % 256;
      data[i + 3] = 255 - ((x * y) % 64);
    }
  }
  return { data, width: w, height: h };
}

const CASES = [];
for (const a of OD.algorithms) CASES.push({ algorithm: a.id });
CASES.push(
  { algorithm: 'floyd-steinberg', serpentine: false },
  { algorithm: 'atkinson', strength: 0.6, palette: 'gray-4' },
  { algorithm: 'floyd-steinberg', colorMode: 'rgb', palette: 'ega-16' },
  { algorithm: 'stucki', colorMode: 'rgb', palette: 'vapor', strength: 0.8 },
  { algorithm: 'bayer-8', colorMode: 'rgb', palette: 'rgb-8', scale: 3 },
  { algorithm: 'halftone-8', palette: 'newsprint', scale: 2 },
  { algorithm: 'atkinson', colorMode: 'rgb', adaptive: 8 },
  { algorithm: 'bayer-4', colorMode: 'rgb', adaptive: 5, scale: 2 },
  { algorithm: 'jarvis-judice-ninke', brightness: 20, contrast: 30, saturation: -20, gamma: 1.4, invert: true },
  { algorithm: 'random', seed: 42, strength: 1.5, palette: 'sunset' },
  { algorithm: 'ign', colorMode: 'rgb', palette: ['#102030', '#f0e0d0', '#ff0055'] },
  { algorithm: 'sierra', brightness: -35, contrast: 60, gamma: 0.7, colorMode: 'rgb', palette: 'pocket-green', scale: 5 }
);

function sha(res) {
  return crypto.createHash('sha256').update(Buffer.from(res.data.buffer, res.data.byteOffset, res.data.byteLength)).digest('hex');
}

function run() {
  const img = testImage(64, 48);
  return CASES.map((settings) => ({ settings, sha256: sha(OD.dither(img, settings)) }));
}

if (process.argv.includes('--write')) {
  const out = {
    description: 'Reference outputs. Image: 64x48 RGBA, r=floor(x*255/63), g=floor(y*255/47), b=(x*x+3*x*y)%256, a=255-((x*y)%64). Hash = sha256 of output RGBA bytes.',
    width: 64,
    height: 48,
    cases: run()
  };
  fs.writeFileSync(VECTORS, JSON.stringify(out, null, 2) + '\n');
  console.log(`wrote ${out.cases.length} vectors to ${VECTORS}`);
} else {
  const ref = JSON.parse(fs.readFileSync(VECTORS, 'utf8'));
  const img = testImage(ref.width, ref.height);
  let fail = 0;
  for (const c of ref.cases) {
    const got = sha(OD.dither(img, c.settings));
    if (got !== c.sha256) { fail++; console.log('FAIL', JSON.stringify(c.settings)); }
  }
  console.log(`${ref.cases.length - fail}/${ref.cases.length} vectors match`);
  process.exit(fail ? 1 : 0);
}
