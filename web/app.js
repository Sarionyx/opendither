/* OpenDither web app */
(function () {
  'use strict';
  var OD = window.OpenDither;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var dpr = window.devicePixelRatio || 1;

  var ICONS = {
    hand: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"><path d="M6 10V5.2a1.2 1.2 0 0 1 2.4 0V9m0-4.8V3.7a1.2 1.2 0 0 1 2.4 0V9m0-4.6a1.2 1.2 0 0 1 2.4 0V9.5m0-3a1.2 1.2 0 0 1 2.4 0v5.3c0 3.3-2.4 5.7-5.6 5.7-2.2 0-3.4-.9-4.6-2.6L3.2 11.6a1.3 1.3 0 0 1 2-1.6L6 11"/></svg>',
    zoom: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8.5" cy="8.5" r="5.5"/><path d="M12.6 12.6 17 17M6 8.5h5M8.5 6v5" stroke-linecap="round"/></svg>',
    compare: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.4"><rect x="2.5" y="3.5" width="15" height="13" rx="1.5"/><path d="M10 1.5v17"/><path d="M10.7 3.5h5.3a1.5 1.5 0 0 1 1.5 1.5v10a1.5 1.5 0 0 1-1.5 1.5h-5.3z" fill="currentColor" stroke="none" opacity=".55"/></svg>',
    original: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M1.8 10S5 4.5 10 4.5 18.2 10 18.2 10 15 15.5 10 15.5 1.8 10 1.8 10z"/><circle cx="10" cy="10" r="2.6"/></svg>'
  };
  var TOOL_NAMES = { hand: 'Hand Tool', zoom: 'Zoom Tool', compare: 'Compare Tool' };
  var ZOOM_STEPS = [1 / 16, 1 / 12, 1 / 8, 1 / 6, 1 / 4, 1 / 3, 1 / 2, 2 / 3, 1, 2, 3, 4, 5, 6, 8, 12, 16, 24, 32, 48, 64];

  // ------------------------------------------------------------------ state
  var state = {
    settings: Object.assign({}, OD.defaults),
    presetId: '1-bit',
    colors: OD.palettes[0].colors.slice(),
    extracted: null,
    image: null, name: 'Untitled', result: null,
    view: { zoom: 1, x: 0, y: 0 },
    tool: 'hand', compare: false, split: 0.5, showOriginal: false,
    exportScale: 1, exportFormat: 'image/png'
  };

  var el = {
    viewport: $('#viewport'), stage: $('#stage'), orig: $('#origCanvas'), out: $('#outCanvas'), split: $('#split'),
    empty: $('#empty'), tabs: $('#docTabs'), tabLabel: $('#tabLabel'), title: $('#docTitle'), busy: $('#busy'),
    zoomInput: $('#zoomInput'), compareToggle: $('#compareToggle'), nav: $('#navCanvas'), navView: $('#navView'),
    navRect: $('#navRect'), navZoom: $('#navZoom'), props: $('#propsPane')
  };

  // ------------------------------------------------------------------ rendering engine (worker with fallback)
  var worker = null, busy = false, pending = false, jobId = 0, engine = 'main thread';

  function initWorker() {
    try {
      var src = 'var OpenDither=(' + OD.__factorySource + ')();var img=null;' +
        'onmessage=function(e){var m=e.data;if(m.type==="load"){img=m.image;return;}' +
        'try{var r=OpenDither.dither(img,m.settings);postMessage({id:m.id,data:r.data,width:r.width,height:r.height,palette:r.palette,ms:r.ms},[r.data.buffer]);}' +
        'catch(err){postMessage({id:m.id,error:String(err&&err.message||err)});}};';
      var url = URL.createObjectURL(new Blob([src], { type: 'text/javascript' }));
      worker = new Worker(url);
      worker.onmessage = function (e) { onResult(e.data); };
      worker.onerror = function () {
        worker = null; engine = 'main thread'; busy = false; updateStatus(); requestRender();
      };
      engine = 'web worker';
    } catch (e) { worker = null; engine = 'main thread'; }
  }

  function recipe() {
    var s = Object.assign({}, state.settings);
    s.palette = state.presetId || state.colors.slice();
    return s;
  }

  function requestRender() {
    if (!state.image) return;
    if (busy) { pending = true; return; }
    busy = true;
    var id = ++jobId, settings = recipe();
    var t = setTimeout(function () { el.busy.hidden = false; }, 120);
    var done = function (msg) { clearTimeout(t); el.busy.hidden = true; return msg; };
    if (worker) {
      worker.__done = done;
      worker.postMessage({ type: 'render', id: id, settings: settings });
    } else {
      setTimeout(function () {
        var msg;
        try { var r = OD.dither(state.image, settings); msg = { id: id, data: r.data, width: r.width, height: r.height, palette: r.palette, ms: r.ms }; }
        catch (err) { msg = { id: id, error: String(err.message || err) }; }
        onResult(done(msg));
      }, 0);
    }
  }

  function onResult(msg) {
    if (worker && worker.__done) worker.__done(msg);
    busy = false;
    if (msg.error) toast(msg.error);
    else if (state.image && msg.width === state.image.width && msg.height === state.image.height) {
      var img = new ImageData(new Uint8ClampedArray(msg.data), msg.width, msg.height);
      el.out.getContext('2d').putImageData(img, 0, 0);
      state.result = img;
      state.extracted = state.settings.adaptive ? msg.palette : null;
      state.lastMs = msg.ms;
      state.lastPalette = msg.palette;
      if (state.settings.adaptive) renderSwatches();
      updateSwatchStack();
      drawNavigator();
      updateStatus();
    }
    if (pending) { pending = false; requestRender(); }
  }

  // ------------------------------------------------------------------ properties panel UI
  var syncers = [];
  function onSync(fn) { syncers.push(fn); return fn; }
  function syncAll() { syncers.forEach(function (f) { f(); }); }

  function h(tag, attrs, children) {
    var n = document.createElement(tag);
    for (var k in attrs || {}) {
      if (k === 'class') n.className = attrs[k];
      else if (k === 'html') n.innerHTML = attrs[k];
      else if (k === 'text') n.textContent = attrs[k];
      else if (k.slice(0, 2) === 'on') n.addEventListener(k.slice(2), attrs[k]);
      else n.setAttribute(k, attrs[k]);
    }
    (children || []).forEach(function (c) { if (c) n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return n;
  }

  function section(title, extra) {
    var content = h('div', { class: 'section-content' });
    var head = h('button', { class: 'section-head' }, [h('i', { class: 'caret' }), title]);
    if (extra) head.appendChild(extra);
    var sec = h('div', { class: 'section' }, [head, content]);
    head.addEventListener('click', function (e) { if (e.target === head || e.target.classList.contains('caret')) sec.classList.toggle('closed'); });
    el.props.appendChild(sec);
    return content;
  }

  function set(key, value) {
    state.settings[key] = value;
    syncAll();
    requestRender();
  }

  /** Adobe-style slider row: scrubby label, track, numeric field. `mult` maps setting → display. */
  function slider(parent, o) {
    var mult = o.mult || 1;
    var label = h('label', { text: o.label, title: 'Drag to adjust · double-click to reset' });
    var range = h('input', { type: 'range', min: o.min, max: o.max, step: o.step });
    var numIn = h('input', { type: 'number', min: o.min, max: o.max, step: o.step });
    var row = h('div', { class: 'field slider' }, [label, range, numIn]);
    parent.appendChild(row);
    var decimals = String(o.step).indexOf('.') >= 0 ? String(o.step).split('.')[1].length : 0;
    function commit(display) {
      display = Math.min(o.max, Math.max(o.min, Number(display)));
      if (!isFinite(display)) return;
      set(o.key, o.toSetting ? o.toSetting(display) : display / mult);
    }
    range.addEventListener('input', function () { commit(range.value); });
    numIn.addEventListener('change', function () { commit(numIn.value); });
    numIn.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
        e.preventDefault();
        var st = Number(o.step) * (e.shiftKey ? 10 : 1);
        commit(Number(numIn.value) + (e.key === 'ArrowUp' ? st : -st));
      }
    });
    label.addEventListener('dblclick', function () { set(o.key, OD.defaults[o.key]); });
    label.addEventListener('pointerdown', function (e) {
      label.setPointerCapture(e.pointerId);
      var startX = e.clientX, start = Number(range.value), per = (o.max - o.min) / 240;
      function move(ev) {
        var d = (ev.clientX - startX) * per * (ev.shiftKey ? 0.1 : 1);
        commit(Math.round((start + d) / o.step) * o.step);
      }
      function up() { label.removeEventListener('pointermove', move); label.removeEventListener('pointerup', up); }
      label.addEventListener('pointermove', move);
      label.addEventListener('pointerup', up);
    });
    onSync(function () {
      var v = state.settings[o.key];
      var d = o.toDisplay ? o.toDisplay(v) : v * mult;
      range.value = d;
      numIn.value = Number(d).toFixed(decimals);
      range.style.setProperty('--p', ((d - o.min) / (o.max - o.min)) * 100 + '%');
      if (o.enabled) row.classList.toggle('disabled', !o.enabled());
      if (o.labelFn) label.textContent = o.labelFn();
    });
    return row;
  }

  function checkbox(parent, o) {
    var input = h('input', { type: 'checkbox' });
    var lab = h('label', { class: 'check' }, [input, h('span', { class: 'box' }), o.text]);
    var row = h('div', { class: 'field' }, [h('label', { text: o.label || '' }), lab]);
    parent.appendChild(row);
    input.addEventListener('change', function () { set(o.key, input.checked); });
    onSync(function () {
      input.checked = !!state.settings[o.key];
      if (o.visible) row.hidden = !o.visible();
    });
    return row;
  }

  function isDiffusion() { return !!OD.kernels[state.settings.algorithm]; }
  function algoName(id) { var a = OD.algorithms.filter(function (x) { return x.id === id; })[0]; return a ? a.name : id; }

  function buildPanel() {
    // ---- Dither
    var s1 = section('Dither');
    var algoSel = h('select');
    var groups = {};
    OD.algorithms.forEach(function (a) {
      if (!groups[a.group]) { groups[a.group] = h('optgroup', { label: a.group }); algoSel.appendChild(groups[a.group]); }
      groups[a.group].appendChild(h('option', { value: a.id, text: a.name }));
    });
    algoSel.addEventListener('change', function () { set('algorithm', algoSel.value); });
    s1.appendChild(h('div', { class: 'field' }, [h('label', { text: 'Algorithm' }), algoSel]));
    onSync(function () { algoSel.value = state.settings.algorithm; });

    slider(s1, {
      key: 'strength', label: 'Strength', min: 0, max: 200, step: 1, mult: 100,
      labelFn: function () { return isDiffusion() ? 'Diffusion %' : 'Spread %'; },
      enabled: function () { return state.settings.algorithm !== 'threshold'; }
    });
    checkbox(s1, { key: 'serpentine', text: 'Serpentine scan', visible: isDiffusion });

    var seedIn = h('input', { type: 'number', step: 1, value: 1 });
    var seedBtn = h('button', { class: 'btn small', text: 'Shuffle' });
    var seedRow = h('div', { class: 'field' }, [h('label', { text: 'Seed' }), h('div', { class: 'row', style: 'justify-content:stretch' }, [seedIn, seedBtn])]);
    seedIn.style.flex = '1';
    s1.appendChild(seedRow);
    seedIn.addEventListener('change', function () { set('seed', Math.trunc(Number(seedIn.value) || 0)); });
    seedBtn.addEventListener('click', function () { set('seed', Math.floor(Math.random() * 1e6)); });
    onSync(function () { seedIn.value = state.settings.seed; seedRow.hidden = state.settings.algorithm !== 'random'; });

    // ---- Adjustments
    var resetAdj = h('span', { class: 'extra', text: 'Reset', title: 'Reset adjustments', style: 'cursor:pointer' });
    resetAdj.addEventListener('click', function (e) {
      e.stopPropagation();
      ['brightness', 'contrast', 'saturation', 'gamma', 'invert'].forEach(function (k) { state.settings[k] = OD.defaults[k]; });
      syncAll(); requestRender();
    });
    var s2 = section('Adjustments', resetAdj);
    slider(s2, { key: 'brightness', label: 'Brightness', min: -100, max: 100, step: 1 });
    slider(s2, { key: 'contrast', label: 'Contrast', min: -100, max: 100, step: 1 });
    slider(s2, { key: 'saturation', label: 'Saturation', min: -100, max: 100, step: 1, enabled: function () { return state.settings.colorMode === 'rgb'; } });
    slider(s2, { key: 'gamma', label: 'Gamma', min: 0.1, max: 5, step: 0.01 });
    checkbox(s2, { key: 'invert', text: 'Invert' });

    // ---- Color
    var s3 = section('Color');
    var seg = h('div', { class: 'seg' }, [
      h('button', { 'data-v': 'luminance', text: 'Luminance', title: 'Map brightness onto the palette (duotone style)' }),
      h('button', { 'data-v': 'rgb', text: 'RGB', title: 'Match full colors against the palette' })
    ]);
    seg.addEventListener('click', function (e) { var v = e.target.getAttribute('data-v'); if (v) set('colorMode', v); });
    s3.appendChild(h('div', { class: 'field' }, [h('label', { text: 'Mode' }), seg]));
    onSync(function () { $$('button', seg).forEach(function (b) { b.classList.toggle('on', b.getAttribute('data-v') === state.settings.colorMode); }); });

    var palSel = h('select');
    OD.palettes.forEach(function (p) { palSel.appendChild(h('option', { value: p.id, text: p.name + '  (' + p.colors.length + ')' })); });
    palSel.appendChild(h('option', { value: '__custom', text: 'Custom' }));
    palSel.addEventListener('change', function () {
      if (palSel.value === '__custom') { state.presetId = null; }
      else { state.presetId = palSel.value; state.colors = OD.palettes.filter(function (p) { return p.id === palSel.value; })[0].colors.slice(); }
      renderSwatches(); syncAll(); requestRender();
    });
    var palRow = h('div', { class: 'field' }, [h('label', { text: 'Palette' }), palSel]);
    s3.appendChild(palRow);
    onSync(function () { palSel.value = state.presetId || '__custom'; palRow.classList.toggle('disabled', state.settings.adaptive > 0); });

    state.swatchBox = h('div', { class: 'swatches' });
    s3.appendChild(state.swatchBox);
    var hexBtn = h('button', { class: 'btn small', text: 'Edit Hex…' });
    var keepBtn = h('button', { class: 'btn small', text: 'Keep Extracted' });
    hexBtn.addEventListener('click', editHex);
    keepBtn.addEventListener('click', function () {
      if (!state.extracted) return;
      state.colors = state.extracted.slice(); state.presetId = null; state.settings.adaptive = 0;
      renderSwatches(); syncAll(); requestRender();
    });
    s3.appendChild(h('div', { class: 'pal-actions' }, [keepBtn, hexBtn]));
    onSync(function () { keepBtn.hidden = !state.settings.adaptive; });

    slider(s3, {
      key: 'adaptive', label: 'Adaptive', min: 0, max: 64, step: 1,
      toSetting: function (d) { return d < 2 ? 0 : d; },
      labelFn: function () { return state.settings.adaptive ? 'Adaptive' : 'Adaptive (off)'; }
    });

    // ---- Output
    var s4 = section('Output');
    slider(s4, { key: 'scale', label: 'Pixel Size', min: 1, max: 32, step: 1 });
    var exScale = h('select');
    [1, 2, 3, 4, 6, 8].forEach(function (v) { exScale.appendChild(h('option', { value: v, text: v + '×' })); });
    exScale.addEventListener('change', function () { state.exportScale = Number(exScale.value); updateStatus(); });
    s4.appendChild(h('div', { class: 'field' }, [h('label', { text: 'Export Scale' }), exScale]));
    var exFmt = h('select');
    [['image/png', 'PNG'], ['image/webp', 'WebP (lossless)'], ['image/jpeg', 'JPEG']].forEach(function (f) { exFmt.appendChild(h('option', { value: f[0], text: f[1] })); });
    exFmt.addEventListener('change', function () { state.exportFormat = exFmt.value; });
    s4.appendChild(h('div', { class: 'field' }, [h('label', { text: 'Format' }), exFmt]));

    onSync(updateEmbed);
    onSync(updateRecipeBox);
    onSync(updateStatus);
    onSync(updateSwatchStack);
  }

  function renderSwatches() {
    var box = state.swatchBox;
    box.innerHTML = '';
    var adaptive = state.settings.adaptive > 0;
    box.classList.toggle('locked', adaptive);
    var list = adaptive ? (state.extracted || []) : state.colors;
    list.forEach(function (c, i) {
      var sw = h('div', { class: 'sw', style: 'background:' + c, title: c + (adaptive ? ' (extracted)' : ' · click to edit') });
      if (!adaptive) {
        var inp = h('input', { type: 'color', value: c });
        inp.addEventListener('input', function () {
          state.colors[i] = inp.value; state.presetId = null; sw.style.background = inp.value; syncAll(); requestRender();
        });
        var del = h('button', { class: 'del', text: '×', title: 'Remove color' });
        del.addEventListener('click', function (e) {
          e.preventDefault(); e.stopPropagation();
          if (state.colors.length <= 1) return toast('A palette needs at least one color');
          state.colors.splice(i, 1); state.presetId = null; renderSwatches(); syncAll(); requestRender();
        });
        sw.appendChild(inp); sw.appendChild(del);
      }
      box.appendChild(sw);
    });
    if (!adaptive) {
      var add = h('button', { class: 'sw add', text: '+', title: 'Add color' });
      add.addEventListener('click', function () {
        if (state.colors.length >= 256) return;
        state.colors.push('#808080'); state.presetId = null; renderSwatches(); syncAll(); requestRender();
      });
      box.appendChild(add);
    } else if (!list.length) box.appendChild(h('span', { class: 'hint', text: 'Palette appears after render' }));
  }

  function editHex() {
    var ta = h('textarea', { spellcheck: 'false' });
    ta.value = state.colors.join('\n');
    modal('Palette Colors', [h('p', { text: 'One hex color per line (or comma separated). Paste palettes from any palette site.' }), ta], [
      ['Cancel', null],
      ['Apply', function () {
        try {
          var list = OD.resolvePalette(ta.value).map(OD.toHex);
          state.colors = list; state.presetId = null; state.settings.adaptive = 0;
          renderSwatches(); syncAll(); requestRender();
        } catch (e) { toast(e.message); return false; }
      }, true]
    ]);
  }

  function updateSwatchStack() {
    var pal = state.settings.adaptive ? (state.extracted || ['#000', '#fff']) : state.colors;
    $('#fgSwatch').style.background = pal[0];
    $('#bgSwatch').style.background = pal[pal.length - 1];
  }

  // ------------------------------------------------------------------ embed & recipe panes
  var ATTRS = { algorithm: 'algorithm', strength: 'strength', serpentine: 'serpentine', seed: 'seed', scale: 'scale', brightness: 'brightness', contrast: 'contrast', saturation: 'saturation', gamma: 'gamma', invert: 'invert', colorMode: 'color-mode', adaptive: 'adaptive' };
  function updateEmbed() {
    var s = state.settings, attrs = [];
    attrs.push('src="' + (state.image ? state.name.replace(/"/g, '') : 'your-image.jpg') + '"');
    Object.keys(ATTRS).forEach(function (k) {
      if (k === 'algorithm' || s[k] !== OD.defaults[k]) attrs.push(ATTRS[k] + '="' + s[k] + '"');
    });
    if (!s.adaptive) attrs.push('palette="' + (state.presetId || state.colors.join(',')) + '"');
    $('#embedCode').value =
      '<script src="opendither.js"></script>\n<script src="opendither-element.js"></script>\n\n' +
      '<open-dither\n  ' + attrs.join('\n  ') + '\n  alt="">\n</open-dither>';
  }
  function updateRecipeBox() {
    var box = $('#recipeCode');
    if (document.activeElement !== box) box.value = JSON.stringify(recipe(), null, 2);
  }

  function applyRecipe(obj) {
    var s = OD.normalizeSettings(obj);
    var p = s.palette;
    if (typeof p === 'string' && OD.palettes.some(function (x) { return x.id === p; })) {
      state.presetId = p;
      state.colors = OD.palettes.filter(function (x) { return x.id === p; })[0].colors.slice();
    } else {
      state.presetId = null;
      state.colors = OD.resolvePalette(p).map(OD.toHex);
    }
    delete s.palette;
    state.settings = Object.assign({}, OD.defaults, s);
    renderSwatches(); syncAll(); requestRender();
  }

  // ------------------------------------------------------------------ image loading
  function loadFromSource(source, name) {
    var w = source.naturalWidth || source.width, hgt = source.naturalHeight || source.height;
    if (w * hgt > 50e6) { toast('Image is too large (max 50 megapixels)'); return; }
    el.orig.width = el.out.width = w; el.orig.height = el.out.height = hgt;
    var ctx = el.orig.getContext('2d', { willReadFrequently: true });
    ctx.clearRect(0, 0, w, hgt);
    ctx.drawImage(source, 0, 0, w, hgt);
    state.image = ctx.getImageData(0, 0, w, hgt);
    el.out.getContext('2d').clearRect(0, 0, w, hgt);
    state.name = name || 'Untitled';
    state.result = null;
    el.stage.style.width = w + 'px'; el.stage.style.height = hgt + 'px';
    el.empty.hidden = true; el.tabs.hidden = false;
    if (worker) worker.postMessage({ type: 'load', image: { data: state.image.data, width: w, height: hgt } });
    fit();
    syncAll();
    requestRender();
  }

  function loadFile(file) {
    if (!file || !/^image\//.test(file.type)) { if (file) toast('Not an image: ' + file.name); return; }
    var url = URL.createObjectURL(file), img = new Image();
    img.onload = function () { loadFromSource(img, file.name || 'Pasted image.png'); URL.revokeObjectURL(url); };
    img.onerror = function () { toast('Could not read ' + file.name); URL.revokeObjectURL(url); };
    img.src = url;
  }

  function makeSample() {
    var c = document.createElement('canvas'), W = 960, H = 640;
    c.width = W; c.height = H;
    var g = c.getContext('2d');
    var sky = g.createLinearGradient(0, 0, 0, H);
    sky.addColorStop(0, '#1d2b64'); sky.addColorStop(0.55, '#c0587e'); sky.addColorStop(1, '#f8b26a');
    g.fillStyle = sky; g.fillRect(0, 0, W, H);
    var sun = g.createRadialGradient(640, 330, 10, 640, 330, 170);
    sun.addColorStop(0, '#fff7d6'); sun.addColorStop(0.35, '#ffd27a'); sun.addColorStop(1, 'rgba(255,190,110,0)');
    g.fillStyle = sun; g.beginPath(); g.arc(640, 330, 170, 0, 7); g.fill();
    var layers = [['#3b2458', 380, 70, 0.006], ['#2a1a40', 440, 60, 0.011], ['#160f24', 520, 45, 0.018]];
    layers.forEach(function (L, i) {
      g.fillStyle = L[0]; g.beginPath(); g.moveTo(0, H);
      for (var x = 0; x <= W; x += 4) g.lineTo(x, L[1] + Math.sin(x * L[3] + i * 2) * L[2] + Math.sin(x * L[3] * 3.1 + i) * L[2] * 0.35);
      g.lineTo(W, H); g.fill();
    });
    var ball = g.createRadialGradient(205, 215, 8, 240, 250, 120);
    ball.addColorStop(0, '#ffffff'); ball.addColorStop(0.3, '#8fd3ff'); ball.addColorStop(1, '#0b2a5b');
    g.fillStyle = ball; g.beginPath(); g.arc(240, 250, 110, 0, 7); g.fill();
    g.fillStyle = 'rgba(255,255,255,.92)'; g.font = '700 64px Segoe UI, system-ui, sans-serif'; g.textAlign = 'center';
    g.fillText('OpenDither', W / 2, 600);
    loadFromSource(c, 'sample.png');
  }

  function closeDoc() {
    state.image = state.result = null;
    el.empty.hidden = false; el.tabs.hidden = true;
    el.orig.width = el.out.width = 0;
    el.nav.width = 0; el.navRect.style.display = 'none';
    updateStatus();
  }

  // ------------------------------------------------------------------ view (zoom/pan/compare)
  function css(z) { return z / dpr; }

  function applyView() {
    var v = state.view, s = css(v.zoom);
    el.stage.style.transform = 'translate(' + v.x + 'px,' + v.y + 'px) scale(' + s + ')';
    var smooth = v.zoom < 1;
    el.orig.style.imageRendering = el.out.style.imageRendering = smooth ? 'auto' : '';
    el.zoomInput.value = +(v.zoom * 100).toFixed(1);
    el.navZoom.value = Math.round((Math.log2(v.zoom) + 4) * 100);
    if (state.image) {
      var w = state.image.width * s, ht = state.image.height * s;
      el.split.style.left = (v.x + state.split * w) + 'px';
      el.split.style.top = Math.max(0, v.y) + 'px';
      el.split.style.height = Math.max(0, Math.min(el.viewport.clientHeight, v.y + ht) - Math.max(0, v.y)) + 'px';
      el.out.style.clipPath = state.compare ? 'inset(0 0 0 ' + (state.split * 100) + '%)' : '';
    }
    el.out.style.visibility = state.showOriginal ? 'hidden' : '';
    el.viewport.classList.toggle('compare', state.compare && !!state.image);
    drawNavRect();
    updateStatus();
  }

  function zoomAt(z, cx, cy) {
    if (!state.image) return;
    z = Math.min(64, Math.max(1 / 32, z));
    var v = state.view;
    if (cx === undefined) { cx = el.viewport.clientWidth / 2; cy = el.viewport.clientHeight / 2; }
    var ix = (cx - v.x) / css(v.zoom), iy = (cy - v.y) / css(v.zoom);
    v.zoom = z;
    v.x = cx - ix * css(z); v.y = cy - iy * css(z);
    applyView();
  }
  function stepZoom(dir, cx, cy) {
    var z = state.view.zoom, next = z;
    if (dir > 0) { for (var i = 0; i < ZOOM_STEPS.length; i++) if (ZOOM_STEPS[i] > z + 1e-6) { next = ZOOM_STEPS[i]; break; } }
    else { for (var j = ZOOM_STEPS.length - 1; j >= 0; j--) if (ZOOM_STEPS[j] < z - 1e-6) { next = ZOOM_STEPS[j]; break; } }
    zoomAt(next, cx, cy);
  }
  function fit() {
    if (!state.image) return;
    var vw = el.viewport.clientWidth - 48, vh = el.viewport.clientHeight - 48;
    var z = Math.min(vw * dpr / state.image.width, vh * dpr / state.image.height);
    if (z > 1) z = Math.floor(z);
    center(z);
  }
  function center(z) {
    var v = state.view;
    v.zoom = z;
    v.x = Math.round((el.viewport.clientWidth - state.image.width * css(z)) / 2);
    v.y = Math.round((el.viewport.clientHeight - state.image.height * css(z)) / 2);
    applyView();
  }

  function setTool(t) {
    state.tool = t;
    $$('#toolbar [data-tool]').forEach(function (b) { b.classList.toggle('active', b.getAttribute('data-tool') === t); });
    el.viewport.className = 'viewport tool-' + t + (state.compare && state.image ? ' compare' : '');
    $('#toolIndicator').innerHTML = ICONS[t] + '<span>' + TOOL_NAMES[t] + '</span>';
    if (t === 'compare' && !state.compare) setCompare(true);
  }
  function setCompare(on) {
    state.compare = on; el.compareToggle.checked = on;
    applyView();
  }

  var spaceDown = false, drag = null;
  el.viewport.addEventListener('pointerdown', function (e) {
    if (!state.image) return;
    var r = el.viewport.getBoundingClientRect(), cx = e.clientX - r.left, cy = e.clientY - r.top;
    var pan = e.button === 1 || spaceDown || state.tool === 'hand';
    if (state.tool === 'zoom' && !spaceDown && e.button === 0) { stepZoom(e.altKey ? -1 : 1, cx, cy); return; }
    el.viewport.setPointerCapture(e.pointerId);
    if (pan) { drag = { mode: 'pan', sx: e.clientX, sy: e.clientY, vx: state.view.x, vy: state.view.y }; el.viewport.classList.add('panning'); }
    else if (state.tool === 'compare') { drag = { mode: 'split' }; moveSplit(cx); }
    e.preventDefault();
  });
  el.viewport.addEventListener('pointermove', function (e) {
    if (!drag) return;
    if (drag.mode === 'pan') {
      state.view.x = drag.vx + e.clientX - drag.sx; state.view.y = drag.vy + e.clientY - drag.sy; applyView();
    } else moveSplit(e.clientX - el.viewport.getBoundingClientRect().left);
  });
  el.viewport.addEventListener('pointerup', function () { drag = null; el.viewport.classList.remove('panning'); });
  function moveSplit(cx) {
    var w = state.image.width * css(state.view.zoom);
    state.split = Math.min(1, Math.max(0, (cx - state.view.x) / w));
    applyView();
  }
  el.viewport.addEventListener('wheel', function (e) {
    if (!state.image) return;
    e.preventDefault();
    var r = el.viewport.getBoundingClientRect();
    if (e.shiftKey && !e.ctrlKey) { state.view.x -= e.deltaY; applyView(); return; }
    var factor = Math.exp(-e.deltaY * (e.deltaMode === 1 ? 0.05 : 0.0018));
    zoomAt(state.view.zoom * factor, e.clientX - r.left, e.clientY - r.top);
  }, { passive: false });
  window.addEventListener('resize', function () { applyView(); });

  // ------------------------------------------------------------------ navigator
  function drawNavigator() {
    var src = state.result ? el.out : el.orig;
    if (!state.image) return;
    var bw = el.navView.clientWidth - 8, bh = el.navView.clientHeight - 8;
    var s = Math.min(bw / state.image.width, bh / state.image.height);
    var w = Math.max(1, Math.round(state.image.width * s)), ht = Math.max(1, Math.round(state.image.height * s));
    el.nav.width = w; el.nav.height = ht;
    var g = el.nav.getContext('2d');
    g.imageSmoothingEnabled = true; g.imageSmoothingQuality = 'high';
    g.drawImage(src, 0, 0, w, ht);
    state.navScale = s;
    drawNavRect();
  }
  function drawNavRect() {
    if (!state.image || !state.navScale) { el.navRect.style.display = 'none'; return; }
    var v = state.view, s = css(v.zoom), ns = state.navScale;
    var x0 = Math.max(0, -v.x / s), y0 = Math.max(0, -v.y / s);
    var x1 = Math.min(state.image.width, (el.viewport.clientWidth - v.x) / s), y1 = Math.min(state.image.height, (el.viewport.clientHeight - v.y) / s);
    if (x1 <= x0 || y1 <= y0) { el.navRect.style.display = 'none'; return; }
    var offX = (el.navView.clientWidth - el.nav.width) / 2, offY = (el.navView.clientHeight - el.nav.height) / 2;
    el.navRect.style.display = 'block';
    el.navRect.style.left = offX + x0 * ns + 'px'; el.navRect.style.top = offY + y0 * ns + 'px';
    el.navRect.style.width = (x1 - x0) * ns + 'px'; el.navRect.style.height = (y1 - y0) * ns + 'px';
  }
  function navJump(e) {
    if (!state.image || !state.navScale) return;
    var r = el.nav.getBoundingClientRect();
    var ix = (e.clientX - r.left) / state.navScale, iy = (e.clientY - r.top) / state.navScale, s = css(state.view.zoom);
    state.view.x = el.viewport.clientWidth / 2 - ix * s; state.view.y = el.viewport.clientHeight / 2 - iy * s;
    applyView();
  }
  el.navView.addEventListener('pointerdown', function (e) {
    el.navView.setPointerCapture(e.pointerId); navJump(e);
    var mv = function (ev) { navJump(ev); };
    el.navView.addEventListener('pointermove', mv);
    el.navView.addEventListener('pointerup', function up() { el.navView.removeEventListener('pointermove', mv); el.navView.removeEventListener('pointerup', up); });
  });
  el.navZoom.addEventListener('input', function () { zoomAt(Math.pow(2, el.navZoom.value / 100 - 4)); });

  // ------------------------------------------------------------------ status bar
  function updateStatus() {
    var s = state.settings;
    $('#stZoom').textContent = state.image ? +(state.view.zoom * 100).toFixed(1) + '%' : '—';
    $('#stSize').textContent = state.image ? state.image.width + ' × ' + state.image.height + ' px' + (state.exportScale > 1 ? '  →  export ' + state.image.width * state.exportScale + ' × ' + state.image.height * state.exportScale : '') : 'No document';
    $('#stAlgo').textContent = algoName(s.algorithm) + (s.scale > 1 ? ' · ' + s.scale + 'px' : '') + ' · ' + (s.colorMode === 'rgb' ? 'RGB' : 'Luminance');
    var nColors = s.adaptive || state.colors.length;
    $('#stPalette').textContent = nColors + ' colors' + (s.adaptive ? ' (adaptive)' : '');
    $('#stTime').textContent = state.result && state.lastMs !== undefined ? Math.round(state.lastMs) + ' ms' : '';
    $('#stEngine').textContent = engine;
    var label = state.name + ' @ ' + +(state.view.zoom * 100).toFixed(1) + '% (' + algoName(s.algorithm) + ', ' + nColors + ' colors)';
    el.tabLabel.textContent = label;
    el.title.textContent = state.image ? label + ' — OpenDither' : 'OpenDither';
    document.title = state.image ? state.name + ' — OpenDither' : 'OpenDither';
  }

  // ------------------------------------------------------------------ export, copy, recipes
  function exportCanvas() {
    var k = state.exportScale, src = el.out;
    if (k === 1) return src;
    var c = document.createElement('canvas');
    c.width = src.width * k; c.height = src.height * k;
    var g = c.getContext('2d');
    g.imageSmoothingEnabled = false;
    g.drawImage(src, 0, 0, c.width, c.height);
    return c;
  }
  function baseName() { return state.name.replace(/\.[^.]+$/, '') || 'image'; }
  function download(blob, name) {
    var a = h('a', { href: URL.createObjectURL(blob), download: name });
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 2000);
  }
  function doExport() {
    if (!state.result) return toast('Open an image first');
    var ext = { 'image/png': 'png', 'image/webp': 'webp', 'image/jpeg': 'jpg' }[state.exportFormat];
    exportCanvas().toBlob(function (b) {
      if (!b) return toast('Export failed');
      download(b, baseName() + '-dithered.' + ext);
    }, state.exportFormat, state.exportFormat === 'image/webp' ? 1 : 0.95);
  }
  function doCopy() {
    if (!state.result) return toast('Nothing to copy');
    if (!navigator.clipboard || !window.ClipboardItem) return toast('Clipboard not available here');
    exportCanvas().toBlob(function (b) {
      navigator.clipboard.write([new ClipboardItem({ 'image/png': b })]).then(function () { toast('Copied to clipboard'); }, function () { toast('Copy was blocked by the browser'); });
    }, 'image/png');
  }
  function doPaste() {
    if (!navigator.clipboard || !navigator.clipboard.read) return toast('Use Ctrl+V to paste');
    navigator.clipboard.read().then(function (items) {
      for (var i = 0; i < items.length; i++) {
        var t = items[i].types.filter(function (x) { return /^image\//.test(x); })[0];
        if (t) return items[i].getType(t).then(function (b) { loadFile(new File([b], 'Pasted image.png', { type: t })); });
      }
      toast('No image on the clipboard');
    }, function () { toast('Use Ctrl+V to paste'); });
  }
  function saveRecipe() {
    download(new Blob([JSON.stringify(recipe(), null, 2)], { type: 'application/json' }), baseName() + '.recipe.json');
  }

  // ------------------------------------------------------------------ dialogs
  function modal(title, bodyNodes, buttons) {
    var m = $('#modal'), body = $('#modalBody'), foot = $('#modalFoot');
    $('#modalTitle').textContent = title;
    body.innerHTML = ''; foot.innerHTML = '';
    bodyNodes.forEach(function (n) { body.appendChild(typeof n === 'string' ? h('p', { html: n }) : n); });
    (buttons || [['Close', null, true]]).forEach(function (b) {
      var btn = h('button', { class: 'btn' + (b[2] ? ' primary' : ''), text: b[0] });
      btn.addEventListener('click', function () { if (b[1] && b[1]() === false) return; m.hidden = true; });
      foot.appendChild(btn);
    });
    m.hidden = false;
  }
  $('#modal').addEventListener('click', function (e) { if (e.target.id === 'modal' || e.target.hasAttribute('data-close')) $('#modal').hidden = true; });

  var toastTimer;
  function toast(msg) {
    var t = $('#toast'); t.textContent = msg; t.hidden = false;
    clearTimeout(toastTimer); toastTimer = setTimeout(function () { t.hidden = true; }, 2600);
  }

  function shortcuts() {
    var rows = [['Open image', 'Ctrl+O'], ['Export', 'Ctrl+S'], ['Copy result', 'Ctrl+C'], ['Paste image', 'Ctrl+V'],
      ['Hand tool', 'H  (or hold Space)'], ['Zoom tool', 'Z  (Alt-click zooms out)'], ['Compare tool', 'C'],
      ['Show original', 'hold \\'], ['Zoom in / out', 'Ctrl + / Ctrl −  or mouse wheel'], ['Fit / 100%', 'Ctrl+0 / Ctrl+1'],
      ['Fine-tune a slider', 'drag its label, Shift for precision'], ['Reset a slider', 'double-click its label']];
    var t = h('table');
    rows.forEach(function (r) { t.appendChild(h('tr', {}, [h('td', { text: r[0] }), h('td', { text: r[1] })])); });
    modal('Keyboard Shortcuts', [t]);
  }
  function about() {
    modal('About OpenDither', [
      '<b>OpenDither ' + OD.version + '</b> — free and open-source dithering for everyone.',
      'The same engine ships as a JavaScript library, an <code>&lt;open-dither&gt;</code> web component, and a Python desktop app and CLI. Recipes are portable between all of them.',
      'MIT licensed. Rendering engine: ' + engine + '.'
    ]);
  }

  // ------------------------------------------------------------------ commands, menus, keyboard
  var COMMANDS = {
    open: function () { $('#fileInput').click(); },
    sample: makeSample,
    export: doExport,
    copy: doCopy,
    paste: doPaste,
    close: closeDoc,
    reset: function () { applyRecipe(OD.defaults); toast('Settings reset'); },
    'import-recipe': function () { $('#recipeInput').click(); },
    'export-recipe': saveRecipe,
    'zoom-in': function () { stepZoom(1); },
    'zoom-out': function () { stepZoom(-1); },
    fit: fit,
    actual: function () { if (state.image) zoomAt(1); },
    compare: function () { setCompare(!state.compare); },
    'toggle-original': function () { state.showOriginal = !state.showOriginal; $('#origBtn').classList.toggle('active', state.showOriginal); applyView(); },
    shortcuts: shortcuts,
    about: about
  };
  function run(cmd) { if (COMMANDS[cmd]) COMMANDS[cmd](); }

  document.addEventListener('click', function (e) {
    var cmdEl = e.target.closest('[data-cmd]');
    var menu = e.target.closest('.menu');
    if (menu && e.target.parentElement === menu) {
      var open = menu.classList.contains('open');
      $$('.menu').forEach(function (m) { m.classList.remove('open'); });
      if (!open) menu.classList.add('open');
      return;
    }
    $$('.menu').forEach(function (m) { m.classList.remove('open'); });
    if (cmdEl) run(cmdEl.getAttribute('data-cmd'));
  });
  $$('.menu').forEach(function (m) {
    m.addEventListener('mouseenter', function () {
      if ($$('.menu.open').length && !m.classList.contains('open')) { $$('.menu').forEach(function (x) { x.classList.remove('open'); }); m.classList.add('open'); }
    });
  });
  $$('#toolbar [data-tool]').forEach(function (b) { b.addEventListener('click', function () { setTool(b.getAttribute('data-tool')); }); });
  el.compareToggle.addEventListener('change', function () { setCompare(el.compareToggle.checked); });
  el.zoomInput.addEventListener('change', function () { zoomAt(Number(el.zoomInput.value) / 100); });

  $$('.panel-tabs [data-tab]').forEach(function (t) {
    t.addEventListener('click', function () {
      var group = t.closest('.panel-group');
      $$('[data-tab]', group).forEach(function (x) { x.classList.toggle('active', x === t); });
      $$('[data-pane]', group).forEach(function (p) { p.hidden = p.getAttribute('data-pane') !== t.getAttribute('data-tab'); });
      if (t.getAttribute('data-tab') === 'recipe') updateRecipeBox();
    });
  });
  $('#copyEmbed').addEventListener('click', function () { copyText($('#embedCode').value); });
  $('#copyRecipe').addEventListener('click', function () { copyText($('#recipeCode').value); });
  $('#applyRecipe').addEventListener('click', function () {
    try { applyRecipe(JSON.parse($('#recipeCode').value)); toast('Recipe applied'); } catch (e) { toast('Invalid JSON: ' + e.message); }
  });
  function copyText(t) {
    (navigator.clipboard ? navigator.clipboard.writeText(t) : Promise.reject()).then(function () { toast('Copied'); }, function () { toast('Select the text and press Ctrl+C'); });
  }

  $('#fileInput').addEventListener('change', function (e) { loadFile(e.target.files[0]); e.target.value = ''; });
  $('#recipeInput').addEventListener('change', function (e) {
    var f = e.target.files[0]; e.target.value = '';
    if (!f) return;
    f.text().then(function (t) { try { applyRecipe(JSON.parse(t)); toast('Recipe loaded'); } catch (err) { toast('Invalid recipe: ' + err.message); } });
  });

  ['dragenter', 'dragover'].forEach(function (ev) {
    el.viewport.addEventListener(ev, function (e) { e.preventDefault(); el.viewport.classList.add('dragover'); });
  });
  ['dragleave', 'drop'].forEach(function (ev) {
    el.viewport.addEventListener(ev, function (e) { e.preventDefault(); el.viewport.classList.remove('dragover'); });
  });
  el.viewport.addEventListener('drop', function (e) {
    var f = e.dataTransfer.files[0];
    if (f && /json$/.test(f.name)) f.text().then(function (t) { try { applyRecipe(JSON.parse(t)); toast('Recipe loaded'); } catch (err) { toast('Invalid recipe'); } });
    else loadFile(f);
  });
  window.addEventListener('dragover', function (e) { e.preventDefault(); });
  window.addEventListener('drop', function (e) { e.preventDefault(); });

  document.addEventListener('paste', function (e) {
    if (/INPUT|TEXTAREA/.test(document.activeElement.tagName)) return;
    var items = e.clipboardData && e.clipboardData.items || [];
    for (var i = 0; i < items.length; i++) if (items[i].type.indexOf('image/') === 0) { loadFile(items[i].getAsFile()); e.preventDefault(); return; }
  });

  document.addEventListener('keydown', function (e) {
    var typing = /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName) && document.activeElement.type !== 'checkbox' && document.activeElement.type !== 'range';
    var mod = e.ctrlKey || e.metaKey;
    if (mod && !typing) {
      var k = e.key.toLowerCase();
      var map = { o: 'open', s: 'export', c: 'copy', '0': 'fit', '1': 'actual', '=': 'zoom-in', '+': 'zoom-in', '-': 'zoom-out' };
      if (k === 'v') return; // handled by paste event
      if (map[k]) { e.preventDefault(); run(map[k]); }
      return;
    }
    if (mod && e.key.toLowerCase() === 'o') { e.preventDefault(); run('open'); return; }
    if (typing) return;
    if (e.key === 'Escape') { $('#modal').hidden = true; $$('.menu').forEach(function (m) { m.classList.remove('open'); }); }
    if (e.code === 'Space' && !spaceDown) { spaceDown = true; el.viewport.classList.add('tool-hand'); e.preventDefault(); }
    if (e.key === 'h' || e.key === 'H') setTool('hand');
    if (e.key === 'z' || e.key === 'Z') setTool('zoom');
    if (e.key === 'c' || e.key === 'C') { if (state.tool === 'compare') setCompare(!state.compare); else setTool('compare'); }
    if (e.key === '\\' && !state.showOriginal) { state.showOriginal = true; applyView(); }
    if (e.key === 'Alt') { el.viewport.classList.add('alt'); e.preventDefault(); }
  });
  document.addEventListener('keyup', function (e) {
    if (e.code === 'Space') { spaceDown = false; el.viewport.classList.toggle('tool-hand', state.tool === 'hand'); }
    if (e.key === '\\') { state.showOriginal = false; applyView(); }
    if (e.key === 'Alt') el.viewport.classList.remove('alt');
  });

  // ------------------------------------------------------------------ boot
  $$('#toolbar [data-tool]').forEach(function (b) { b.innerHTML = ICONS[b.getAttribute('data-tool')]; });
  $('#origBtn').innerHTML = ICONS.original;
  initWorker();
  buildPanel();
  renderSwatches();
  setTool('hand');
  syncAll();
  applyView();

  // Expose for debugging / automation
  window.OpenDitherApp = { state: state, loadFromSource: loadFromSource, applyRecipe: applyRecipe, makeSample: makeSample };
})();
