/*!
 * OpenDither core — https://github.com/ (your repo here)
 * MIT License. Zero dependencies. Works in browsers (<script>), Web Workers and Node (require).
 * Implements spec/ALGORITHMS.md; outputs must match spec/test-vectors.json.
 */
(function (root, factory) {
  var api = factory();
  // Lets the web app build a Web Worker from this file even when opened from file://
  api.__factorySource = factory.toString();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.OpenDither = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  var VERSION = '1.0.0';

  // ---------------------------------------------------------------- data

  var PALETTES = [
    { id: '1-bit', name: '1-bit', colors: ['#000000', '#ffffff'] },
    { id: 'gray-4', name: 'Gray 4', colors: ['#000000', '#555555', '#aaaaaa', '#ffffff'] },
    { id: 'gray-8', name: 'Gray 8', colors: ['#000000', '#242424', '#494949', '#6d6d6d', '#929292', '#b6b6b6', '#dbdbdb', '#ffffff'] },
    { id: 'pocket-green', name: 'Pocket Green', colors: ['#0f380f', '#306230', '#8bac0f', '#9bbc0f'] },
    { id: 'amber', name: 'Amber Terminal', colors: ['#1a0f00', '#ffb000'] },
    { id: 'phosphor', name: 'Green Phosphor', colors: ['#001a00', '#33ff33'] },
    { id: 'newsprint', name: 'Newsprint', colors: ['#1b1b1b', '#f2ecd9'] },
    { id: 'blueprint', name: 'Blueprint', colors: ['#0b3d91', '#e6f0ff'] },
    { id: 'riso', name: 'Riso Pink', colors: ['#1d1d1b', '#ff48b0', '#f6f1e7'] },
    { id: 'cyanotype', name: 'Cyanotype', colors: ['#0d1f3c', '#1f4e8c', '#5b8fc7', '#dfeaf5'] },
    { id: 'sepia', name: 'Sepia', colors: ['#2b1d0e', '#7a5230', '#c49a6c', '#f3e3c3'] },
    { id: 'sunset', name: 'Sunset', colors: ['#2b0f3a', '#a4245f', '#f2643a', '#fdd56b'] },
    { id: 'vapor', name: 'Vapor', colors: ['#1a1033', '#ff71ce', '#01cdfe', '#05ffa1', '#fffb96'] },
    { id: 'cga', name: 'CGA Mode 1', colors: ['#000000', '#55ffff', '#ff55ff', '#ffffff'] },
    { id: 'rgb-8', name: 'RGB 8', colors: ['#000000', '#ff0000', '#00ff00', '#0000ff', '#00ffff', '#ff00ff', '#ffff00', '#ffffff'] },
    { id: 'ega-16', name: 'EGA 16', colors: ['#000000', '#0000aa', '#00aa00', '#00aaaa', '#aa0000', '#aa00aa', '#aa5500', '#aaaaaa', '#555555', '#5555ff', '#55ff55', '#55ffff', '#ff5555', '#ff55ff', '#ffff55', '#ffffff'] }
  ];

  var KERNELS = {
    'floyd-steinberg': [16, [[1, 0, 7], [-1, 1, 3], [0, 1, 5], [1, 1, 1]]],
    'false-floyd-steinberg': [8, [[1, 0, 3], [0, 1, 3], [1, 1, 2]]],
    'jarvis-judice-ninke': [48, [[1, 0, 7], [2, 0, 5], [-2, 1, 3], [-1, 1, 5], [0, 1, 7], [1, 1, 5], [2, 1, 3], [-2, 2, 1], [-1, 2, 3], [0, 2, 5], [1, 2, 3], [2, 2, 1]]],
    'stucki': [42, [[1, 0, 8], [2, 0, 4], [-2, 1, 2], [-1, 1, 4], [0, 1, 8], [1, 1, 4], [2, 1, 2], [-2, 2, 1], [-1, 2, 2], [0, 2, 4], [1, 2, 2], [2, 2, 1]]],
    'burkes': [32, [[1, 0, 8], [2, 0, 4], [-2, 1, 2], [-1, 1, 4], [0, 1, 8], [1, 1, 4], [2, 1, 2]]],
    'sierra': [32, [[1, 0, 5], [2, 0, 3], [-2, 1, 2], [-1, 1, 4], [0, 1, 5], [1, 1, 4], [2, 1, 2], [-1, 2, 2], [0, 2, 3], [1, 2, 2]]],
    'sierra-two-row': [16, [[1, 0, 4], [2, 0, 3], [-2, 1, 1], [-1, 1, 2], [0, 1, 3], [1, 1, 2], [2, 1, 1]]],
    'sierra-lite': [4, [[1, 0, 2], [-1, 1, 1], [0, 1, 1]]],
    'atkinson': [8, [[1, 0, 1], [2, 0, 1], [-1, 1, 1], [0, 1, 1], [1, 1, 1], [0, 2, 1]]]
  };

  var ALGORITHMS = [
    { id: 'threshold', name: 'Threshold', group: 'None' },
    { id: 'floyd-steinberg', name: 'Floyd–Steinberg', group: 'Error diffusion' },
    { id: 'false-floyd-steinberg', name: 'False Floyd–Steinberg', group: 'Error diffusion' },
    { id: 'jarvis-judice-ninke', name: 'Jarvis–Judice–Ninke', group: 'Error diffusion' },
    { id: 'stucki', name: 'Stucki', group: 'Error diffusion' },
    { id: 'burkes', name: 'Burkes', group: 'Error diffusion' },
    { id: 'sierra', name: 'Sierra', group: 'Error diffusion' },
    { id: 'sierra-two-row', name: 'Sierra Two-Row', group: 'Error diffusion' },
    { id: 'sierra-lite', name: 'Sierra Lite', group: 'Error diffusion' },
    { id: 'atkinson', name: 'Atkinson', group: 'Error diffusion' },
    { id: 'bayer-2', name: 'Bayer 2×2', group: 'Ordered' },
    { id: 'bayer-4', name: 'Bayer 4×4', group: 'Ordered' },
    { id: 'bayer-8', name: 'Bayer 8×8', group: 'Ordered' },
    { id: 'bayer-16', name: 'Bayer 16×16', group: 'Ordered' },
    { id: 'cluster-4', name: 'Clustered Dot 4×4', group: 'Ordered' },
    { id: 'halftone-8', name: 'Halftone 8×8', group: 'Ordered' },
    { id: 'lines-h', name: 'Lines Horizontal', group: 'Ordered' },
    { id: 'lines-v', name: 'Lines Vertical', group: 'Ordered' },
    { id: 'diagonal', name: 'Diagonal Lines', group: 'Ordered' },
    { id: 'random', name: 'Random Noise', group: 'Noise' },
    { id: 'ign', name: 'Interleaved Gradient', group: 'Noise' }
  ];

  var DEFAULTS = {
    algorithm: 'floyd-steinberg',
    strength: 1,
    serpentine: true,
    seed: 1,
    scale: 1,
    brightness: 0,
    contrast: 0,
    saturation: 0,
    gamma: 1,
    invert: false,
    colorMode: 'luminance',
    palette: '1-bit',
    adaptive: 0
  };

  // ---------------------------------------------------------------- helpers

  function clamp(v, lo, hi) { return v < lo ? lo : v > hi ? hi : v; }
  function num(v, d) { v = Number(v); return isFinite(v) ? v : d; }
  function bool(v, d) {
    if (v === undefined || v === null) return d;
    if (typeof v === 'string') return !(v === 'false' || v === '0' || v === 'off' || v === '');
    return !!v;
  }

  function parseColor(c) {
    if (Array.isArray(c)) return [clamp(c[0] | 0, 0, 255), clamp(c[1] | 0, 0, 255), clamp(c[2] | 0, 0, 255)];
    var s = String(c).trim().replace(/^#/, '');
    if (s.length === 3) s = s[0] + s[0] + s[1] + s[1] + s[2] + s[2];
    if (!/^[0-9a-fA-F]{6}$/.test(s)) throw new Error('OpenDither: invalid color "' + c + '"');
    var n = parseInt(s, 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }

  function toHex(rgb) {
    return '#' + rgb.map(function (v) { return (v | 0).toString(16).padStart(2, '0'); }).join('');
  }

  function findPalette(id) {
    for (var i = 0; i < PALETTES.length; i++) if (PALETTES[i].id === id) return PALETTES[i];
    return null;
  }

  /** Accepts a preset id, an array of colors, or a comma/space separated string of hex colors. */
  function resolvePalette(p) {
    if (typeof p === 'string') {
      var preset = findPalette(p.trim());
      if (preset) return preset.colors.map(parseColor);
      p = p.split(/[\s,;]+/).filter(Boolean);
    }
    if (!Array.isArray(p) || p.length === 0) return findPalette('1-bit').colors.map(parseColor);
    return p.map(parseColor);
  }

  function normalizeSettings(s) {
    s = s || {};
    var o = {};
    var algo = s.algorithm || DEFAULTS.algorithm;
    var known = ALGORITHMS.some(function (a) { return a.id === algo; });
    o.algorithm = known ? algo : DEFAULTS.algorithm;
    o.strength = clamp(num(s.strength, 1), 0, 2);
    o.serpentine = bool(s.serpentine, true);
    o.seed = Math.trunc(num(s.seed, 1));
    o.scale = clamp(Math.trunc(num(s.scale, 1)), 1, 64);
    o.brightness = clamp(num(s.brightness, 0), -100, 100);
    o.contrast = clamp(num(s.contrast, 0), -100, 100);
    o.saturation = clamp(num(s.saturation, 0), -100, 100);
    o.gamma = clamp(num(s.gamma, 1), 0.1, 5);
    o.invert = bool(s.invert, false);
    o.colorMode = s.colorMode === 'rgb' ? 'rgb' : 'luminance';
    o.palette = s.palette !== undefined ? s.palette : DEFAULTS.palette;
    var ad = clamp(Math.trunc(num(s.adaptive, 0)), 0, 256);
    o.adaptive = ad < 2 ? 0 : ad;
    return o;
  }

  // ---------------------------------------------------------------- matrices

  function bayer(n) {
    var m = [[0]];
    for (var size = 1; size < n; size *= 2) {
      var next = [];
      for (var y = 0; y < size * 2; y++) next.push(new Array(size * 2));
      for (var yy = 0; yy < size; yy++) {
        for (var xx = 0; xx < size; xx++) {
          var b = m[yy][xx] * 4;
          next[yy][xx] = b;
          next[yy][xx + size] = b + 2;
          next[yy + size][xx] = b + 3;
          next[yy + size][xx + size] = b + 1;
        }
      }
      m = next;
    }
    return m;
  }

  function rankedMatrix(n, f) {
    var b = bayer(n), cells = [];
    for (var y = 0; y < n; y++) for (var x = 0; x < n; x++) cells.push([f(x, y, n), b[y][x], y * n + x]);
    cells.sort(function (a, c) { return (a[0] - c[0]) || (a[1] - c[1]) || (a[2] - c[2]); });
    var t = new Float64Array(n * n);
    for (var r = 0; r < cells.length; r++) t[cells[r][2]] = (r + 0.5) / (n * n);
    return t;
  }

  var MATRIX_DEFS = {
    'bayer-2': 2, 'bayer-4': 4, 'bayer-8': 8, 'bayer-16': 16,
    'cluster-4': [4, function (x, y, n) { var X = 2 * x + 1, Y = 2 * y + 1; return (X - n) * (X - n) + (Y - n) * (Y - n); }],
    'halftone-8': [8, function (x, y, n) {
      var X = 2 * x + 1, Y = 2 * y + 1;
      var dc = (X - n) * (X - n) + (Y - n) * (Y - n);
      var dk = Math.min(X * X, (2 * n - X) * (2 * n - X)) + Math.min(Y * Y, (2 * n - Y) * (2 * n - Y));
      return Math.min(dc, dk);
    }],
    'lines-h': [4, function (x, y, n) { return Math.abs(2 * y + 1 - n); }],
    'lines-v': [4, function (x, y, n) { return Math.abs(2 * x + 1 - n); }],
    'diagonal': [8, function (x, y, n) { return Math.abs(2 * ((x + y) % n) + 1 - n); }]
  };
  var matrixCache = {};

  function getMatrix(id) {
    if (matrixCache[id]) return matrixCache[id];
    var def = MATRIX_DEFS[id], n, t;
    if (typeof def === 'number') {
      n = def;
      var b = bayer(n);
      t = new Float64Array(n * n);
      for (var y = 0; y < n; y++) for (var x = 0; x < n; x++) t[y * n + x] = (b[y][x] + 0.5) / (n * n);
    } else {
      n = def[0];
      t = rankedMatrix(n, def[1]);
    }
    return (matrixCache[id] = { n: n, t: t });
  }

  function lowbias32(x) {
    x = x >>> 0;
    x ^= x >>> 16; x = Math.imul(x, 0x7feb352d);
    x ^= x >>> 15; x = Math.imul(x, 0x846ca68b);
    x ^= x >>> 16;
    return x >>> 0;
  }

  function lum(r, g, b) { return 0.299 * r + 0.587 * g + 0.114 * b; }

  // ---------------------------------------------------------------- pipeline stages

  function downscale(src, w, h, s) {
    var w2 = Math.ceil(w / s), h2 = Math.ceil(h / s);
    var out = new Float64Array(w2 * h2 * 3);
    if (s === 1) {
      for (var i = 0, j = 0; i < w * h; i++, j += 4) {
        out[i * 3] = src[j]; out[i * 3 + 1] = src[j + 1]; out[i * 3 + 2] = src[j + 2];
      }
      return { buf: out, w: w2, h: h2 };
    }
    for (var by = 0; by < h2; by++) {
      var y1 = Math.min((by + 1) * s, h);
      for (var bx = 0; bx < w2; bx++) {
        var x1 = Math.min((bx + 1) * s, w), r = 0, g = 0, b = 0, c = 0;
        for (var y = by * s; y < y1; y++) {
          for (var x = bx * s; x < x1; x++) {
            var k = (y * w + x) * 4;
            r += src[k]; g += src[k + 1]; b += src[k + 2]; c++;
          }
        }
        var o = (by * w2 + bx) * 3;
        out[o] = r / c; out[o + 1] = g / c; out[o + 2] = b / c;
      }
    }
    return { buf: out, w: w2, h: h2 };
  }

  function adjust(buf, s) {
    var br = s.brightness, ct = s.contrast, sat = s.saturation, gm = s.gamma, inv = s.invert;
    var bOff = br * 2.55;
    var ck = (100 + ct) / 100, cf = ck * ck;
    var sk = 1 + sat / 100;
    var ig = 1 / gm;
    var n = buf.length;
    for (var i = 0; i < n; i += 3) {
      var r = buf[i], g = buf[i + 1], b = buf[i + 2];
      if (br !== 0) { r = r + bOff; g = g + bOff; b = b + bOff; }
      if (ct !== 0) { r = (r - 127.5) * cf + 127.5; g = (g - 127.5) * cf + 127.5; b = (b - 127.5) * cf + 127.5; }
      if (sat !== 0) {
        var L = 0.299 * r + 0.587 * g + 0.114 * b;
        r = L + (r - L) * sk; g = L + (g - L) * sk; b = L + (b - L) * sk;
      }
      if (gm !== 1) {
        r = 255 * Math.pow(clamp(r, 0, 255) / 255, ig);
        g = 255 * Math.pow(clamp(g, 0, 255) / 255, ig);
        b = 255 * Math.pow(clamp(b, 0, 255) / 255, ig);
      }
      if (inv) { r = 255 - r; g = 255 - g; b = 255 - b; }
      buf[i] = clamp(r, 0, 255); buf[i + 1] = clamp(g, 0, 255); buf[i + 2] = clamp(b, 0, 255);
    }
  }

  /** Median-cut palette from an RGB Float64Array buffer. Returns [[r,g,b], ...]. */
  function medianCut(buf, count, n) {
    var stride = count <= 65536 ? 1 : Math.ceil(count / 65536);
    var first = [];
    for (var i = 0; i < count; i += stride) first.push(i);
    var boxes = [first];
    while (boxes.length < n) {
      var best = -1, bestScore = 0, bestCh = 0;
      for (var bi = 0; bi < boxes.length; bi++) {
        var box = boxes[bi];
        if (box.length < 2) continue;
        var score = -1, ch = 0;
        for (var c = 0; c < 3; c++) {
          var lo = Infinity, hi = -Infinity;
          for (var k = 0; k < box.length; k++) {
            var v = buf[box[k] * 3 + c];
            if (v < lo) lo = v;
            if (v > hi) hi = v;
          }
          if (hi - lo > score) { score = hi - lo; ch = c; }
        }
        if (score > bestScore) { bestScore = score; best = bi; bestCh = ch; }
      }
      if (best < 0) break;
      var target = boxes[best].slice();
      var sc = bestCh;
      target.sort(function (a, b) { return buf[a * 3 + sc] - buf[b * 3 + sc]; });
      var m = Math.floor(target.length / 2);
      boxes[best] = target.slice(0, m);
      boxes.push(target.slice(m));
    }
    return boxes.map(function (box) {
      var rgb = [0, 0, 0];
      for (var c = 0; c < 3; c++) {
        var sum = 0;
        for (var k = 0; k < box.length; k++) sum += buf[box[k] * 3 + c];
        rgb[c] = Math.floor(sum / box.length + 0.5);
      }
      return rgb;
    });
  }

  function spreadOf(pv, k, C) {
    if (k < 2) return 0;
    var total = 0;
    for (var i = 0; i < k; i++) {
      var best = Infinity;
      for (var j = 0; j < k; j++) {
        if (j === i) continue;
        var d = 0;
        for (var c = 0; c < C; c++) { var dd = pv[i * C + c] - pv[j * C + c]; d += dd * dd; }
        if (d < best) best = d;
      }
      total += Math.sqrt(best);
    }
    var mean = total / k;
    return C === 3 ? mean / Math.sqrt(3) : mean;
  }

  function nearest(v, o, pv, k, C) {
    var best = 0, bestD = Infinity;
    for (var i = 0; i < k; i++) {
      var d = 0;
      for (var c = 0; c < C; c++) { var dd = v[o + c] - pv[i * C + c]; d += dd * dd; }
      if (d < bestD) { bestD = d; best = i; }
    }
    return best;
  }

  function errorDiffuse(buf, w, h, C, pv, k, kernel, serpentine, strength, out) {
    var div = kernel[0], ent = kernel[1], ne = ent.length;
    var dxs = new Int32Array(ne), dys = new Int32Array(ne), cf = new Float64Array(ne);
    for (var q = 0; q < ne; q++) { dxs[q] = ent[q][0]; dys[q] = ent[q][1]; cf[q] = ent[q][2] / div; }
    var e = new Float64Array(C);
    for (var y = 0; y < h; y++) {
      var rev = serpentine && (y % 2 === 1);
      for (var i = 0; i < w; i++) {
        var x = rev ? w - 1 - i : i;
        var o = (y * w + x) * C;
        var p = nearest(buf, o, pv, k, C);
        out[y * w + x] = p;
        for (var c = 0; c < C; c++) e[c] = (buf[o + c] - pv[p * C + c]) * strength;
        for (q = 0; q < ne; q++) {
          var nx = x + (rev ? -dxs[q] : dxs[q]), ny = y + dys[q];
          if (nx < 0 || nx >= w || ny >= h) continue;
          var no = (ny * w + nx) * C, co = cf[q];
          for (c = 0; c < C; c++) buf[no + c] += e[c] * co;
        }
      }
    }
  }

  function thresholdDither(buf, w, h, C, pv, k, s, out) {
    var algo = s.algorithm, spread = spreadOf(pv, k, C);
    var mat = MATRIX_DEFS[algo] !== undefined ? getMatrix(algo) : null;
    var seedHash = lowbias32(s.seed >>> 0);
    var v = new Float64Array(C);
    for (var y = 0; y < h; y++) {
      var rowHash = lowbias32((seedHash ^ y) >>> 0);
      for (var x = 0; x < w; x++) {
        var t;
        if (mat) t = mat.t[(y % mat.n) * mat.n + (x % mat.n)];
        else if (algo === 'random') t = lowbias32((rowHash ^ x) >>> 0) / 4294967296;
        else if (algo === 'ign') { var f = 0.06711056 * x + 0.00583715 * y; f = 52.9829189 * (f - Math.floor(f)); t = f - Math.floor(f); }
        else t = 0.5;
        var off = algo === 'threshold' ? 0 : (t - 0.5) * s.strength * spread;
        var o = (y * w + x) * C;
        for (var c = 0; c < C; c++) v[c] = buf[o + c] + off;
        out[y * w + x] = nearest(v, 0, pv, k, C);
      }
    }
  }

  // ---------------------------------------------------------------- public API

  /**
   * Dither an image.
   * @param {{data: Uint8ClampedArray|Uint8Array, width: number, height: number}} image RGBA pixels (ImageData works)
   * @param {object} options recipe, see spec/ALGORITHMS.md
   * @returns {{data: Uint8ClampedArray, width: number, height: number, palette: string[], settings: object, ms: number}}
   */
  function dither(image, options) {
    var t0 = (typeof performance !== 'undefined' ? performance : Date).now();
    var s = normalizeSettings(options);
    var w = image.width, h = image.height, src = image.data;
    if (!w || !h || !src || src.length < w * h * 4) throw new Error('OpenDither: expected RGBA image data');

    var ds = downscale(src, w, h, s.scale);
    var buf = ds.buf, w2 = ds.w, h2 = ds.h, n = w2 * h2;
    adjust(buf, s);

    var pal = s.adaptive >= 2 ? medianCut(buf, n, s.adaptive) : resolvePalette(s.palette);
    var k = pal.length, C, pv, work;
    if (s.colorMode === 'luminance') {
      C = 1;
      pv = new Float64Array(k);
      for (var i = 0; i < k; i++) pv[i] = lum(pal[i][0], pal[i][1], pal[i][2]);
      work = new Float64Array(n);
      for (i = 0; i < n; i++) work[i] = lum(buf[i * 3], buf[i * 3 + 1], buf[i * 3 + 2]);
    } else {
      C = 3;
      pv = new Float64Array(k * 3);
      for (i = 0; i < k; i++) { pv[i * 3] = pal[i][0]; pv[i * 3 + 1] = pal[i][1]; pv[i * 3 + 2] = pal[i][2]; }
      work = buf;
    }

    var idx = new Uint16Array(n);
    if (KERNELS[s.algorithm]) errorDiffuse(work, w2, h2, C, pv, k, KERNELS[s.algorithm], s.serpentine, s.strength, idx);
    else thresholdDither(work, w2, h2, C, pv, k, s, idx);

    var out = new Uint8ClampedArray(w * h * 4), sc = s.scale;
    for (var y = 0; y < h; y++) {
      var row = Math.floor(y / sc) * w2;
      for (var x = 0; x < w; x++) {
        var p = pal[idx[row + Math.floor(x / sc)]], j = (y * w + x) * 4;
        out[j] = p[0]; out[j + 1] = p[1]; out[j + 2] = p[2]; out[j + 3] = src[j + 3];
      }
    }
    var t1 = (typeof performance !== 'undefined' ? performance : Date).now();
    return { data: out, width: w, height: h, palette: pal.map(toHex), settings: s, ms: t1 - t0 };
  }

  /** Browser helper: dither an <img>, <canvas>, ImageBitmap or <video> frame, returns a new canvas. */
  function ditherToCanvas(source, options, canvas) {
    var w = source.naturalWidth || source.videoWidth || source.width;
    var h = source.naturalHeight || source.videoHeight || source.height;
    var tmp = document.createElement('canvas');
    tmp.width = w; tmp.height = h;
    var tctx = tmp.getContext('2d', { willReadFrequently: true });
    tctx.drawImage(source, 0, 0, w, h);
    var res = dither(tctx.getImageData(0, 0, w, h), options);
    canvas = canvas || document.createElement('canvas');
    canvas.width = w; canvas.height = h;
    canvas.getContext('2d').putImageData(new ImageData(res.data, w, h), 0, 0);
    return canvas;
  }

  return {
    version: VERSION,
    dither: dither,
    ditherToCanvas: ditherToCanvas,
    normalizeSettings: normalizeSettings,
    resolvePalette: resolvePalette,
    parseColor: parseColor,
    toHex: toHex,
    medianCut: medianCut,
    getMatrix: getMatrix,
    lowbias32: lowbias32,
    algorithms: ALGORITHMS,
    palettes: PALETTES,
    kernels: KERNELS,
    defaults: DEFAULTS
  };
});
