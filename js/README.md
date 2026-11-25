# OpenDither for JavaScript

Zero-dependency dithering library and web component. Works in browsers (plain `<script>`), Web
Workers, bundlers and Node.

## `<open-dither>` element

```html
<script src="opendither.js"></script>
<script src="opendither-element.js"></script>

<open-dither src="photo.jpg" algorithm="atkinson" palette="newsprint" scale="2" alt="Portrait"></open-dither>
```

| attribute | values | default |
|---|---|---|
| `src` | image URL (same origin, or served with CORS headers) | |
| `alt` | accessible description | |
| `algorithm` | see `OpenDither.algorithms` | `floyd-steinberg` |
| `palette` | preset id (`1-bit`, `newsprint`, `vapor`…) or `#hex,#hex,…` | `1-bit` |
| `color-mode` | `luminance` or `rgb` | `luminance` |
| `scale` | pixel size, 1–64 | `1` |
| `strength` | 0–2 | `1` |
| `serpentine` | `true` / `false` | `true` |
| `seed` | integer (`random` algorithm) | `1` |
| `brightness`, `contrast`, `saturation` | -100–100 | `0` |
| `gamma` | 0.1–5 | `1` |
| `invert` | `true` / `false` | `false` |
| `adaptive` | 2–256 to extract a palette from the image, 0 = off | `0` |
| `settings` | a full JSON recipe | |
| `max-size` | limit the long side before dithering (faster on big photos) | |
| `reveal` | `hover` shows the original under the cursor | |

Changing an attribute re-renders. Images render when they scroll near the viewport. Events: `render`
(`detail.ms`, `detail.palette`) and `error`. Method: `element.toBlob()`.

## `OpenDither.auto()`

Upgrade ordinary images in place, keeping your existing CSS and layout:

```html
<img src="hero.jpg" alt="…" data-dither="bayer-4" data-palette="sepia" data-scale="2" data-color-mode="rgb">
<script>OpenDither.auto()</script>
```

`data-dither` is the algorithm id or a full JSON recipe. Other settings use `data-*` names from the
table above. `OpenDither.auto(selector, defaults)` accepts a custom selector and default settings.

## Library API

```js
const OpenDither = require('opendither');        // Node / bundlers; in browsers it's a global

const result = OpenDither.dither(imageData, {    // anything with {data: RGBA, width, height}
  algorithm: 'jarvis-judice-ninke',
  colorMode: 'rgb',
  palette: ['#0f380f', '#306230', '#8bac0f', '#9bbc0f'],
  scale: 2
});
// result: { data: Uint8ClampedArray, width, height, palette: ['#…'], settings, ms }

const canvas = OpenDither.ditherToCanvas(document.querySelector('img'), { algorithm: 'atkinson' });
```

Also exported: `algorithms`, `palettes`, `defaults`, `kernels`, `normalizeSettings`,
`resolvePalette`, `parseColor`, `toHex`, `medianCut`, `getMatrix`.

## Tests

```bash
npm test   # checks spec/test-vectors.json and behaviour tests
```
