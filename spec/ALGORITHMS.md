# OpenDither algorithm specification

This document is the contract every OpenDither implementation (JavaScript, Python, and any future
port) follows. Two implementations given the same image and the same **recipe** must produce the
same pixels. `spec/test-vectors.json` holds SHA-256 hashes of reference outputs; a port is
conformant when it reproduces them.

All arithmetic is IEEE-754 double precision unless stated otherwise. When an expression is written
below, evaluate it in the order written (left to right) so results match bit for bit.

## 1. Recipe (settings)

A recipe is a JSON object. Missing keys take the default.

| key           | type                     | default             | range / values |
|---------------|--------------------------|---------------------|----------------|
| `algorithm`   | string                   | `"floyd-steinberg"` | see §6 |
| `strength`    | number                   | `1`                 | 0 – 2. Error-diffusion amount, or pattern spread for ordered/noise |
| `serpentine`  | boolean                  | `true`              | error diffusion only |
| `seed`        | integer                  | `1`                 | `random` only |
| `scale`       | integer                  | `1`                 | 1 – 64. Pixel size |
| `brightness`  | number                   | `0`                 | -100 – 100 |
| `contrast`    | number                   | `0`                 | -100 – 100 |
| `saturation`  | number                   | `0`                 | -100 – 100 |
| `gamma`       | number                   | `1`                 | 0.1 – 5 |
| `invert`      | boolean                  | `false`             | |
| `colorMode`   | string                   | `"luminance"`       | `"luminance"` or `"rgb"` |
| `palette`     | string or array          | `"1-bit"`           | preset id (`spec/palettes.json`) or array of `"#rrggbb"` / `"#rgb"` strings |
| `adaptive`    | integer                  | `0`                 | 0 = off, 2 – 256 = build palette from the image with median cut (§5) |

Numbers outside their range are clamped. `scale`, `seed` and `adaptive` are truncated to integers
(`adaptive` of 1 counts as 0).

## 2. Pipeline

1. **Downscale** by `scale` (§3) → working buffer `W` of RGB doubles, size `w2 × h2`.
2. **Adjust** every pixel of `W` (§4).
3. **Palette**: if `adaptive ≥ 2`, median cut on `W` (§5); otherwise the recipe palette.
4. **Channels**: in `luminance` mode replace each pixel by `L = 0.299*r + 0.587*g + 0.114*b`
   (one channel), and each palette color by the same formula. In `rgb` mode keep three channels.
5. **Dither + quantize** into palette indices (§6–§8).
6. **Upscale** with nearest neighbour: output pixel `(x, y)` takes index
   `I[floor(y/scale) * w2 + floor(x/scale)]`, writes that palette color's RGB, and keeps the
   **source alpha** of pixel `(x, y)`.

## 3. Downscale

`w2 = ceil(w / scale)`, `h2 = ceil(h / scale)`. Working pixel `(bx, by)` is the mean of source pixels
`x ∈ [bx*scale, min((bx+1)*scale, w))`, `y ∈ [by*scale, min((by+1)*scale, h))` per channel
(sum of integer values divided by the pixel count). With `scale = 1` the buffer is the source RGB.

## 4. Adjustments

Applied per pixel to `r, g, b` in this order. Steps whose parameter is at its neutral value are
skipped.

1. brightness `b ≠ 0`: `v = v + b * 2.55`
2. contrast `c ≠ 0`: `k = (100 + c) / 100`, `f = k * k`, `v = (v - 127.5) * f + 127.5`
3. saturation `s ≠ 0`: `L = 0.299*r + 0.587*g + 0.114*b` (from the current values),
   `k = 1 + s / 100`, `v = L + (v - L) * k`
4. gamma `g ≠ 1`: clamp `v` to [0, 255], `ig = 1 / g`, `v = 255 * pow(v / 255, ig)`
5. invert: `v = 255 - v`
6. clamp `v` to [0, 255]

## 5. Adaptive palette (median cut)

1. Samples: let `n = w2*h2`. If `n ≤ 65536`, use every pixel, else every `ceil(n / 65536)`-th
   pixel in raster order starting at index 0.
2. Start with one box holding all samples (in raster order).
3. Repeat while the number of boxes is below `adaptive`:
   - For every box with at least 2 samples, compute per-channel `range = max - min`; the box's
     score is its largest range and its split channel is the lowest channel index (r, g, b) that has
     that range.
   - Pick the box with the highest score (ties: lowest box index). Stop if no box has score > 0.
   - Stable-sort that box's samples by the split channel. Let `m = floor(len / 2)`. The first `m`
     samples replace the box at its index; the rest are appended as a new box.
4. Each box's color is, per channel, `floor(mean + 0.5)` where `mean` is the sum of the box's
   samples in box order, added sequentially, divided by the count.

## 6. Algorithms

| id | group | notes |
|----|-------|-------|
| `threshold` | none | nearest palette color, no dithering |
| `floyd-steinberg`, `false-floyd-steinberg`, `jarvis-judice-ninke`, `stucki`, `burkes`, `sierra`, `sierra-two-row`, `sierra-lite`, `atkinson` | error diffusion | §7 |
| `bayer-2`, `bayer-4`, `bayer-8`, `bayer-16`, `cluster-4`, `halftone-8`, `lines-h`, `lines-v`, `diagonal` | ordered | §8 |
| `random` | noise | seeded hash noise |
| `ign` | noise | interleaved gradient noise |

**Nearest color**: squared Euclidean distance over the active channels, accumulated as
`d = 0; d += dd*dd` per channel in order. Ties go to the lowest palette index.

## 7. Error diffusion

Kernels are lists of `(dx, dy, weight)` with a divisor. The coefficient is `weight / divisor`.

| kernel | divisor | entries `(dx,dy,w)` |
|---|---|---|
| floyd-steinberg | 16 | (1,0,7) (-1,1,3) (0,1,5) (1,1,1) |
| false-floyd-steinberg | 8 | (1,0,3) (0,1,3) (1,1,2) |
| jarvis-judice-ninke | 48 | (1,0,7) (2,0,5) (-2,1,3) (-1,1,5) (0,1,7) (1,1,5) (2,1,3) (-2,2,1) (-1,2,3) (0,2,5) (1,2,3) (2,2,1) |
| stucki | 42 | (1,0,8) (2,0,4) (-2,1,2) (-1,1,4) (0,1,8) (1,1,4) (2,1,2) (-2,2,1) (-1,2,2) (0,2,4) (1,2,2) (2,2,1) |
| burkes | 32 | (1,0,8) (2,0,4) (-2,1,2) (-1,1,4) (0,1,8) (1,1,4) (2,1,2) |
| sierra | 32 | (1,0,5) (2,0,3) (-2,1,2) (-1,1,4) (0,1,5) (1,1,4) (2,1,2) (-1,2,2) (0,2,3) (1,2,2) |
| sierra-two-row | 16 | (1,0,4) (2,0,3) (-2,1,1) (-1,1,2) (0,1,3) (1,1,2) (2,1,1) |
| sierra-lite | 4 | (1,0,2) (-1,1,1) (0,1,1) |
| atkinson | 8 | (1,0,1) (2,0,1) (-1,1,1) (0,1,1) (1,1,1) (0,2,1) |

Rows are processed top to bottom. With `serpentine`, odd rows (`y % 2 == 1`) run right to left and
every `dx` is negated. For each pixel: pick the nearest palette color `p` for the current values
`v`, then for each channel `e = (v - p) * strength` and for each kernel entry inside the image
`buf[neighbor] += e * coef`. Values are **not** clamped during propagation.

## 8. Ordered and noise dithering

Each pixel gets a threshold `t ∈ [0, 1)`. Every channel becomes `v + (t - 0.5) * strength * spread`,
then the nearest palette color is chosen. `threshold` uses no offset.

**Spread**: for each palette color, the distance to its nearest *other* palette color (Euclidean in
`rgb` mode, absolute luminance difference in `luminance` mode). `spread` is the mean of those
distances (summed in palette order, divided by count), divided by `sqrt(3)` in `rgb` mode. A
one-color palette has spread 0.

**Matrices** (`t = M[y mod n][x mod n]`):

- `bayer-n` (n = 2, 4, 8, 16): `B1 = [[0]]`, `B2k = [[4B, 4B+2], [4B+3, 4B+1]]`;
  `t = (B + 0.5) / n²`.
- Generated matrices rank the `n²` cells by `(f, bayer_n value, y*n + x)` ascending and set
  `t = (rank + 0.5) / n²`. With `X = 2x + 1`, `Y = 2y + 1` (integers):
  - `cluster-4` (n=4): `f = (X - n)² + (Y - n)²`
  - `halftone-8` (n=8): `f = min((X - n)² + (Y - n)², min(X², (2n - X)²) + min(Y², (2n - Y)²))`
  - `lines-h` (n=4): `f = |Y - n|`
  - `lines-v` (n=4): `f = |X - n|`
  - `diagonal` (n=8): `f = |2*((x + y) mod n) + 1 - n|`

**Noise**:

- `random`: with 32-bit unsigned arithmetic and
  `lowbias32(x) = x ^= x>>16; x *= 0x7feb352d; x ^= x>>15; x *= 0x846ca68b; x ^= x>>16`,
  `h = lowbias32(lowbias32(lowbias32(seed) ^ y) ^ x)`, `t = h / 2³²`.
- `ign`: `t = fract(52.9829189 * fract(0.06711056*x + 0.00583715*y))`, `fract(v) = v - floor(v)`.

`x, y` are working-buffer coordinates (after downscale).
