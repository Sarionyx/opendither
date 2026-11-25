/*!
 * OpenDither for websites — MIT License.
 * Load after opendither.js. Provides:
 *   1. <open-dither src="photo.jpg" algorithm="atkinson" palette="#000,#fff" scale="2"></open-dither>
 *   2. OpenDither.auto()  — dithers every <img data-dither> on the page in place.
 */
(function () {
  'use strict';
  if (typeof window === 'undefined') return;
  var OD = window.OpenDither;
  if (!OD) { console.warn('[OpenDither] load opendither.js before opendither-element.js'); return; }

  // attribute / data-* name -> recipe key
  var KEYS = {
    algorithm: 'algorithm', strength: 'strength', serpentine: 'serpentine', seed: 'seed', scale: 'scale',
    brightness: 'brightness', contrast: 'contrast', saturation: 'saturation', gamma: 'gamma', invert: 'invert',
    'color-mode': 'colorMode', palette: 'palette', adaptive: 'adaptive'
  };
  var DATA_KEYS = { colorMode: 'colorMode' };

  function settingsFrom(get) {
    var s = {};
    var json = get('settings') || get('recipe');
    if (json) { try { Object.assign(s, JSON.parse(json)); } catch (e) { console.warn('[OpenDither] invalid settings JSON', e); } }
    Object.keys(KEYS).forEach(function (attr) {
      var v = get(attr);
      if (v !== null && v !== undefined && v !== '') s[KEYS[attr]] = v;
    });
    return s;
  }

  /** Reads pixels from an image, optionally limiting the long side to maxSize. Throws on tainted (CORS) images. */
  function pixels(img, maxSize) {
    var w = img.naturalWidth, h = img.naturalHeight;
    if (maxSize && Math.max(w, h) > maxSize) {
      var k = maxSize / Math.max(w, h);
      w = Math.max(1, Math.round(w * k)); h = Math.max(1, Math.round(h * k));
    }
    var c = document.createElement('canvas');
    c.width = w; c.height = h;
    var g = c.getContext('2d', { willReadFrequently: true });
    g.drawImage(img, 0, 0, w, h);
    return g.getImageData(0, 0, w, h);
  }

  function whenVisible(node, fn) {
    if (!('IntersectionObserver' in window)) return fn();
    var io = new IntersectionObserver(function (entries) {
      if (entries.some(function (e) { return e.isIntersecting; })) { io.disconnect(); fn(); }
    }, { rootMargin: '300px' });
    io.observe(node);
  }

  // ------------------------------------------------------------------ <open-dither>
  if (window.customElements && !customElements.get('open-dither')) {
    var STYLE =
      ':host{display:inline-block;position:relative;line-height:0;max-width:100%}' +
      ':host([hidden]){display:none}' +
      'canvas,img{display:block;width:100%;height:auto;image-rendering:pixelated;image-rendering:crisp-edges}' +
      '.orig{position:absolute;inset:0;width:100%;height:100%;object-fit:fill;opacity:0;transition:opacity .25s;image-rendering:auto}' +
      ':host([reveal=hover]:hover) .orig{opacity:1}' +
      ':host(.od-fallback) canvas{display:none}:host(.od-fallback) .orig{position:static;opacity:1}';

    class OpenDitherElement extends HTMLElement {
      static get observedAttributes() {
        return ['src', 'alt', 'settings', 'recipe', 'max-size'].concat(Object.keys(KEYS));
      }
      constructor() {
        super();
        var root = this.attachShadow({ mode: 'open' });
        root.innerHTML = '<style>' + STYLE + '</style><canvas part="canvas"></canvas><img class="orig" part="original" alt="">';
        this._canvas = root.querySelector('canvas');
        this._orig = root.querySelector('.orig');
        this._img = null;
        this._queued = false;
      }
      connectedCallback() {
        this.setAttribute('role', 'img');
        if (!this._img) whenVisible(this, this._load.bind(this));
      }
      attributeChangedCallback(name, oldV, newV) {
        if (oldV === newV) return;
        if (name === 'alt') { this.setAttribute('aria-label', newV || ''); return; }
        if (!this.isConnected || !this._img) return;
        if (name === 'src') this._load(); else this.render();
      }
      /** Current recipe built from attributes. */
      get settings() { var self = this; return settingsFrom(function (a) { return self.getAttribute(a); }); }
      set settings(obj) { this.setAttribute('settings', JSON.stringify(obj)); }

      _load() {
        var src = this.getAttribute('src');
        if (!src) return;
        var img = new Image();
        img.decoding = 'async';
        if (!/^(data|blob):/.test(src)) img.crossOrigin = 'anonymous';
        var self = this;
        img.onload = function () { self._img = img; self._orig.src = src; self.render(); };
        img.onerror = function () {
          // Probably a cross-origin image without CORS headers: show it undithered.
          self._orig.src = src; self.classList.add('od-fallback');
          self.dispatchEvent(new CustomEvent('error', { detail: 'Could not load ' + src }));
        };
        img.src = src;
      }

      /** Re-render now (batched to one per frame). */
      render() {
        if (this._queued || !this._img) return;
        this._queued = true;
        var self = this;
        requestAnimationFrame(function () {
          self._queued = false;
          try {
            var data = pixels(self._img, Number(self.getAttribute('max-size')) || 0);
            var res = OD.dither(data, self.settings);
            self._canvas.width = res.width; self._canvas.height = res.height;
            self._canvas.getContext('2d').putImageData(new ImageData(res.data, res.width, res.height), 0, 0);
            self.classList.remove('od-fallback');
            self.dispatchEvent(new CustomEvent('render', { detail: { ms: res.ms, palette: res.palette } }));
          } catch (e) {
            self.classList.add('od-fallback');
            console.warn('[OpenDither] could not dither ' + self.getAttribute('src') + ' — cross-origin images need CORS headers.', e);
          }
        });
      }

      /** Returns the dithered image as a Blob (PNG). */
      toBlob() { var c = this._canvas; return new Promise(function (r) { c.toBlob(r, 'image/png'); }); }
    }
    customElements.define('open-dither', OpenDitherElement);
  }

  // ------------------------------------------------------------------ OpenDither.auto()
  /**
   * Dithers <img> elements in place. Settings come from data-* attributes:
   *   <img src="a.jpg" data-dither="atkinson" data-palette="newsprint" data-scale="2">
   * data-dither may also be a full JSON recipe.
   */
  OD.auto = function (selector, defaults) {
    var imgs = document.querySelectorAll(selector || 'img[data-dither]');
    Array.prototype.forEach.call(imgs, function (img) {
      if (img.dataset.ditherDone) return;
      whenVisible(img, function () { ditherImg(img, defaults); });
    });
  };

  function ditherImg(img, defaults) {
    var raw = img.dataset.dither || '';
    var s = Object.assign({}, defaults || {});
    if (raw.trim().charAt(0) === '{') { try { Object.assign(s, JSON.parse(raw)); } catch (e) { console.warn('[OpenDither] bad data-dither JSON', e); } }
    else if (raw) s.algorithm = raw;
    Object.assign(s, settingsFrom(function (attr) {
      if (attr === 'algorithm' || attr === 'settings' || attr === 'recipe') return null;
      var key = attr.replace(/-([a-z])/g, function (_, c) { return c.toUpperCase(); });
      return img.dataset[DATA_KEYS[key] || key];
    }));
    var original = img.currentSrc || img.src;
    var src = new Image();
    if (!/^(data|blob):/.test(original)) src.crossOrigin = 'anonymous';
    src.onload = function () {
      try {
        var res = OD.dither(pixels(src, Number(img.dataset.maxSize) || 0), s);
        var c = document.createElement('canvas');
        c.width = res.width; c.height = res.height;
        c.getContext('2d').putImageData(new ImageData(res.data, res.width, res.height), 0, 0);
        c.toBlob(function (b) {
          img.dataset.ditherDone = '1';
          img.dataset.originalSrc = original;
          img.removeAttribute('srcset');
          img.style.imageRendering = 'pixelated';
          img.src = URL.createObjectURL(b);
        });
      } catch (e) { console.warn('[OpenDither] could not dither image (CORS?)', original, e); }
    };
    src.src = original;
  }
})();
