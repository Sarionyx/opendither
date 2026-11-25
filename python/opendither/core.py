"""OpenDither core. Implements spec/ALGORITHMS.md; outputs match spec/test-vectors.json."""
from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, field

import numpy as np

from ._diffuse import ENGINE, diffuse
from .palettes import PALETTES, find_palette

__all__ = [
    "ALGORITHMS", "KERNELS", "DEFAULTS", "ENGINE", "DitherResult",
    "dither", "normalize_settings", "resolve_palette", "parse_color", "to_hex",
    "get_matrix", "median_cut", "lowbias32",
]

KERNELS = {
    "floyd-steinberg": (16, [(1, 0, 7), (-1, 1, 3), (0, 1, 5), (1, 1, 1)]),
    "false-floyd-steinberg": (8, [(1, 0, 3), (0, 1, 3), (1, 1, 2)]),
    "jarvis-judice-ninke": (48, [(1, 0, 7), (2, 0, 5), (-2, 1, 3), (-1, 1, 5), (0, 1, 7), (1, 1, 5), (2, 1, 3),
                                 (-2, 2, 1), (-1, 2, 3), (0, 2, 5), (1, 2, 3), (2, 2, 1)]),
    "stucki": (42, [(1, 0, 8), (2, 0, 4), (-2, 1, 2), (-1, 1, 4), (0, 1, 8), (1, 1, 4), (2, 1, 2),
                    (-2, 2, 1), (-1, 2, 2), (0, 2, 4), (1, 2, 2), (2, 2, 1)]),
    "burkes": (32, [(1, 0, 8), (2, 0, 4), (-2, 1, 2), (-1, 1, 4), (0, 1, 8), (1, 1, 4), (2, 1, 2)]),
    "sierra": (32, [(1, 0, 5), (2, 0, 3), (-2, 1, 2), (-1, 1, 4), (0, 1, 5), (1, 1, 4), (2, 1, 2),
                    (-1, 2, 2), (0, 2, 3), (1, 2, 2)]),
    "sierra-two-row": (16, [(1, 0, 4), (2, 0, 3), (-2, 1, 1), (-1, 1, 2), (0, 1, 3), (1, 1, 2), (2, 1, 1)]),
    "sierra-lite": (4, [(1, 0, 2), (-1, 1, 1), (0, 1, 1)]),
    "atkinson": (8, [(1, 0, 1), (2, 0, 1), (-1, 1, 1), (0, 1, 1), (1, 1, 1), (0, 2, 1)]),
}

ALGORITHMS = [
    {"id": "threshold", "name": "Threshold", "group": "None"},
    {"id": "floyd-steinberg", "name": "Floyd–Steinberg", "group": "Error diffusion"},
    {"id": "false-floyd-steinberg", "name": "False Floyd–Steinberg", "group": "Error diffusion"},
    {"id": "jarvis-judice-ninke", "name": "Jarvis–Judice–Ninke", "group": "Error diffusion"},
    {"id": "stucki", "name": "Stucki", "group": "Error diffusion"},
    {"id": "burkes", "name": "Burkes", "group": "Error diffusion"},
    {"id": "sierra", "name": "Sierra", "group": "Error diffusion"},
    {"id": "sierra-two-row", "name": "Sierra Two-Row", "group": "Error diffusion"},
    {"id": "sierra-lite", "name": "Sierra Lite", "group": "Error diffusion"},
    {"id": "atkinson", "name": "Atkinson", "group": "Error diffusion"},
    {"id": "bayer-2", "name": "Bayer 2×2", "group": "Ordered"},
    {"id": "bayer-4", "name": "Bayer 4×4", "group": "Ordered"},
    {"id": "bayer-8", "name": "Bayer 8×8", "group": "Ordered"},
    {"id": "bayer-16", "name": "Bayer 16×16", "group": "Ordered"},
    {"id": "cluster-4", "name": "Clustered Dot 4×4", "group": "Ordered"},
    {"id": "halftone-8", "name": "Halftone 8×8", "group": "Ordered"},
    {"id": "lines-h", "name": "Lines Horizontal", "group": "Ordered"},
    {"id": "lines-v", "name": "Lines Vertical", "group": "Ordered"},
    {"id": "diagonal", "name": "Diagonal Lines", "group": "Ordered"},
    {"id": "random", "name": "Random Noise", "group": "Noise"},
    {"id": "ign", "name": "Interleaved Gradient", "group": "Noise"},
]
_ALGO_IDS = {a["id"] for a in ALGORITHMS}

DEFAULTS = {
    "algorithm": "floyd-steinberg",
    "strength": 1.0,
    "serpentine": True,
    "seed": 1,
    "scale": 1,
    "brightness": 0.0,
    "contrast": 0.0,
    "saturation": 0.0,
    "gamma": 1.0,
    "invert": False,
    "colorMode": "luminance",
    "palette": "1-bit",
    "adaptive": 0,
}

_MASK = 0xFFFFFFFF


# ----------------------------------------------------------------------------- settings

def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def _num(v, default):
    if v is None:
        return default
    try:
        v = float(v)
    except (TypeError, ValueError):
        return default
    return v if math.isfinite(v) else default


def _bool(v, default):
    if v is None:
        return default
    if isinstance(v, str):
        return v.strip().lower() not in ("false", "0", "off", "", "no")
    return bool(v)


def parse_color(c):
    """'#rgb', '#rrggbb', 'rrggbb' or (r, g, b) -> (r, g, b)."""
    if isinstance(c, (list, tuple)):
        return tuple(int(_clamp(int(v), 0, 255)) for v in c[:3])
    s = str(c).strip().lstrip("#")
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", s):
        raise ValueError(f'OpenDither: invalid color "{c}"')
    n = int(s, 16)
    return ((n >> 16) & 255, (n >> 8) & 255, n & 255)


def to_hex(rgb):
    return "#" + "".join(f"{int(v):02x}" for v in rgb[:3])


def resolve_palette(p):
    """Preset id, list of colors, or a comma/space separated string of hex colors."""
    if isinstance(p, str):
        preset = find_palette(p.strip())
        if preset:
            return [parse_color(c) for c in preset["colors"]]
        p = [x for x in re.split(r"[\s,;]+", p) if x]
    if not p:
        return [parse_color(c) for c in find_palette("1-bit")["colors"]]
    return [parse_color(c) for c in p]


def normalize_settings(s=None, **kw):
    s = dict(s or {})
    s.update(kw)
    o = {}
    algo = s.get("algorithm") or DEFAULTS["algorithm"]
    o["algorithm"] = algo if algo in _ALGO_IDS else DEFAULTS["algorithm"]
    o["strength"] = _clamp(_num(s.get("strength"), 1.0), 0.0, 2.0)
    o["serpentine"] = _bool(s.get("serpentine"), True)
    o["seed"] = math.trunc(_num(s.get("seed"), 1))
    o["scale"] = int(_clamp(math.trunc(_num(s.get("scale"), 1)), 1, 64))
    o["brightness"] = _clamp(_num(s.get("brightness"), 0.0), -100.0, 100.0)
    o["contrast"] = _clamp(_num(s.get("contrast"), 0.0), -100.0, 100.0)
    o["saturation"] = _clamp(_num(s.get("saturation"), 0.0), -100.0, 100.0)
    o["gamma"] = _clamp(_num(s.get("gamma"), 1.0), 0.1, 5.0)
    o["invert"] = _bool(s.get("invert"), False)
    o["colorMode"] = "rgb" if s.get("colorMode", s.get("color_mode")) == "rgb" else "luminance"
    o["palette"] = s["palette"] if s.get("palette") is not None else DEFAULTS["palette"]
    ad = int(_clamp(math.trunc(_num(s.get("adaptive"), 0)), 0, 256))
    o["adaptive"] = 0 if ad < 2 else ad
    return o


# ----------------------------------------------------------------------------- matrices & noise

def _bayer(n):
    m = np.zeros((1, 1), dtype=np.int64)
    size = 1
    while size < n:
        nxt = np.zeros((size * 2, size * 2), dtype=np.int64)
        b = m * 4
        nxt[:size, :size] = b
        nxt[:size, size:] = b + 2
        nxt[size:, :size] = b + 3
        nxt[size:, size:] = b + 1
        m = nxt
        size *= 2
    return m


def _f_cluster(x, y, n):
    X, Y = 2 * x + 1, 2 * y + 1
    return (X - n) ** 2 + (Y - n) ** 2


def _f_halftone(x, y, n):
    X, Y = 2 * x + 1, 2 * y + 1
    dc = (X - n) ** 2 + (Y - n) ** 2
    dk = min(X * X, (2 * n - X) ** 2) + min(Y * Y, (2 * n - Y) ** 2)
    return min(dc, dk)


_MATRIX_DEFS = {
    "bayer-2": 2, "bayer-4": 4, "bayer-8": 8, "bayer-16": 16,
    "cluster-4": (4, _f_cluster),
    "halftone-8": (8, _f_halftone),
    "lines-h": (4, lambda x, y, n: abs(2 * y + 1 - n)),
    "lines-v": (4, lambda x, y, n: abs(2 * x + 1 - n)),
    "diagonal": (8, lambda x, y, n: abs(2 * ((x + y) % n) + 1 - n)),
}
_matrix_cache = {}


def get_matrix(algo_id):
    """Returns an (n, n) float64 array of thresholds in [0, 1)."""
    if algo_id in _matrix_cache:
        return _matrix_cache[algo_id]
    d = _MATRIX_DEFS[algo_id]
    if isinstance(d, int):
        n = d
        t = (_bayer(n) + 0.5) / (n * n)
    else:
        n, f = d
        b = _bayer(n)
        cells = sorted((f(x, y, n), int(b[y, x]), y * n + x) for y in range(n) for x in range(n))
        t = np.zeros(n * n)
        for rank, cell in enumerate(cells):
            t[cell[2]] = (rank + 0.5) / (n * n)
        t = t.reshape(n, n)
    _matrix_cache[algo_id] = t
    return t


def lowbias32(x):
    """32-bit integer hash (scalar Python int or numpy uint32 array)."""
    if isinstance(x, np.ndarray):
        x = x.astype(np.uint32)
        x ^= x >> np.uint32(16)
        x *= np.uint32(0x7FEB352D)
        x ^= x >> np.uint32(15)
        x *= np.uint32(0x846CA68B)
        x ^= x >> np.uint32(16)
        return x
    x &= _MASK
    x ^= x >> 16
    x = (x * 0x7FEB352D) & _MASK
    x ^= x >> 15
    x = (x * 0x846CA68B) & _MASK
    x ^= x >> 16
    return x


# ----------------------------------------------------------------------------- pipeline stages

def _to_rgba(image):
    """PIL image or numpy array -> contiguous (h, w, 4) uint8."""
    if hasattr(image, "convert") and hasattr(image, "size"):  # PIL
        return np.asarray(image.convert("RGBA"), dtype=np.uint8)
    a = np.asarray(image)
    if a.dtype != np.uint8:
        a = np.clip(a, 0, 255).astype(np.uint8)
    if a.ndim == 2:
        a = np.stack([a, a, a], axis=-1)
    if a.shape[2] == 3:
        a = np.concatenate([a, np.full(a.shape[:2] + (1,), 255, np.uint8)], axis=2)
    return np.ascontiguousarray(a[:, :, :4])


def _downscale(rgba, s):
    h, w = rgba.shape[:2]
    rgb = rgba[:, :, :3].astype(np.float64)
    if s == 1:
        return rgb
    h2, w2 = -(-h // s), -(-w // s)
    pad = np.zeros((h2 * s, w2 * s, 3))
    pad[:h, :w] = rgb
    sums = pad.reshape(h2, s, w2, s, 3).sum(axis=(1, 3))  # integer sums: exact in float64
    ys = np.minimum((np.arange(h2) + 1) * s, h) - np.arange(h2) * s
    xs = np.minimum((np.arange(w2) + 1) * s, w) - np.arange(w2) * s
    cnt = (ys[:, None] * xs[None, :]).astype(np.float64)
    return sums / cnt[:, :, None]


def _adjust(buf, s):
    r, g, b = buf[:, :, 0], buf[:, :, 1], buf[:, :, 2]
    if s["brightness"] != 0:
        off = s["brightness"] * 2.55
        r, g, b = r + off, g + off, b + off
    if s["contrast"] != 0:
        k = (100 + s["contrast"]) / 100
        f = k * k
        r, g, b = (r - 127.5) * f + 127.5, (g - 127.5) * f + 127.5, (b - 127.5) * f + 127.5
    if s["saturation"] != 0:
        L = 0.299 * r + 0.587 * g + 0.114 * b
        k = 1 + s["saturation"] / 100
        r, g, b = L + (r - L) * k, L + (g - L) * k, L + (b - L) * k
    if s["gamma"] != 1:
        ig = 1 / s["gamma"]
        r = 255 * np.power(np.clip(r, 0, 255) / 255, ig)
        g = 255 * np.power(np.clip(g, 0, 255) / 255, ig)
        b = 255 * np.power(np.clip(b, 0, 255) / 255, ig)
    if s["invert"]:
        r, g, b = 255 - r, 255 - g, 255 - b
    return np.clip(np.stack([r, g, b], axis=-1), 0, 255)


def median_cut(flat, n_colors):
    """Median-cut palette from an (n, 3) float array. Returns [(r, g, b), ...]."""
    count = flat.shape[0]
    stride = 1 if count <= 65536 else math.ceil(count / 65536)
    boxes = [np.arange(0, count, stride)]
    scores = {}

    def score_of(box):
        key = id(box)
        if key not in scores:
            vals = flat[box]
            rng = vals.max(axis=0) - vals.min(axis=0)
            best, ch = -1.0, 0
            for c in range(3):
                if rng[c] > best:
                    best, ch = float(rng[c]), c
            scores[key] = (best, ch, box)  # keep box alive so id() stays unique
        return scores[key][:2]

    while len(boxes) < n_colors:
        best_i, best_score, best_ch = -1, 0.0, 0
        for i, box in enumerate(boxes):
            if len(box) < 2:
                continue
            sc, ch = score_of(box)
            if sc > best_score:
                best_i, best_score, best_ch = i, sc, ch
        if best_i < 0:
            break
        box = boxes[best_i]
        ordered = box[np.argsort(flat[box, best_ch], kind="stable")]
        m = len(ordered) // 2
        boxes[best_i] = ordered[:m]
        boxes.append(ordered[m:])

    colors = []
    for box in boxes:
        rgb = []
        for c in range(3):
            total = float(np.cumsum(flat[box, c])[-1])  # sequential sum, like the JS reference
            rgb.append(math.floor(total / len(box) + 0.5))
        colors.append(tuple(rgb))
    return colors


def _spread(pv, k, C):
    if k < 2:
        return 0.0
    total = 0.0
    for i in range(k):
        best = math.inf
        for j in range(k):
            if j == i:
                continue
            d = 0.0
            for c in range(C):
                dd = pv[i * C + c] - pv[j * C + c]
                d += dd * dd
            if d < best:
                best = d
        total += math.sqrt(best)
    mean = total / k
    return mean / math.sqrt(3) if C == 3 else mean


def _nearest(v, pal):
    """v: (h, w, C) float, pal: (k, C) float -> (h, w) indices. Chunked to bound memory."""
    h, w, C = v.shape
    k = pal.shape[0]
    out = np.empty((h, w), dtype=np.int64)
    rows = max(1, 4_000_000 // max(1, w * k))
    for y0 in range(0, h, rows):
        blk = v[y0:y0 + rows]
        d = None
        for c in range(C):
            dd = blk[:, :, c, None] - pal[None, None, :, c]
            d = dd * dd if d is None else d + dd * dd
        out[y0:y0 + rows] = np.argmin(d, axis=-1)
    return out


def _threshold_map(algo, h, w, seed):
    if algo in _MATRIX_DEFS:
        m = get_matrix(algo)
        n = m.shape[0]
        return m[np.arange(h)[:, None] % n, np.arange(w)[None, :] % n]
    if algo == "random":
        seed_hash = lowbias32(seed & _MASK)
        rows = lowbias32(np.uint32(seed_hash) ^ np.arange(h, dtype=np.uint32))
        hsh = lowbias32(rows[:, None] ^ np.arange(w, dtype=np.uint32)[None, :])
        return hsh.astype(np.float64) / 4294967296.0
    if algo == "ign":
        x = np.arange(w, dtype=np.float64)[None, :]
        y = np.arange(h, dtype=np.float64)[:, None]
        f = 0.06711056 * x + 0.00583715 * y
        f = 52.9829189 * (f - np.floor(f))
        return f - np.floor(f)
    return np.full((h, w), 0.5)


# ----------------------------------------------------------------------------- public API

@dataclass
class DitherResult:
    image: np.ndarray            # (h, w, 4) uint8 RGBA
    palette: list                # hex strings actually used
    settings: dict               # normalized recipe
    ms: float = 0.0
    engine: str = field(default=ENGINE)

    @property
    def width(self):
        return self.image.shape[1]

    @property
    def height(self):
        return self.image.shape[0]

    def to_pil(self):
        from PIL import Image
        return Image.fromarray(self.image, "RGBA")

    def save(self, path, scale=1, **kw):
        img = self.to_pil()
        if scale and scale > 1:
            from PIL import Image
            img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
        if str(path).lower().endswith((".jpg", ".jpeg")):
            img = img.convert("RGB")
        img.save(path, **kw)
        return path


def dither(image, settings=None, **kw):
    """Dither an image.

    image: PIL.Image, or numpy array (h, w), (h, w, 3) or (h, w, 4).
    settings: recipe dict (see spec/ALGORITHMS.md); keyword arguments override it.
    """
    t0 = time.perf_counter()
    s = normalize_settings(settings, **kw)
    rgba = _to_rgba(image)
    h, w = rgba.shape[:2]
    sc = s["scale"]

    buf = _adjust(_downscale(rgba, sc), s)
    h2, w2 = buf.shape[:2]

    pal = median_cut(buf.reshape(-1, 3), s["adaptive"]) if s["adaptive"] >= 2 else resolve_palette(s["palette"])
    k = len(pal)
    pal_f = np.array(pal, dtype=np.float64)
    if s["colorMode"] == "luminance":
        pv = 0.299 * pal_f[:, 0] + 0.587 * pal_f[:, 1] + 0.114 * pal_f[:, 2]
        work = (0.299 * buf[:, :, 0] + 0.587 * buf[:, :, 1] + 0.114 * buf[:, :, 2])[:, :, None]
        pv2 = pv[:, None]
    else:
        pv2 = pal_f
        work = buf
    C = pv2.shape[1]

    algo = s["algorithm"]
    if algo in KERNELS:
        idx = diffuse(np.ascontiguousarray(work, dtype=np.float64).reshape(-1), w2, h2, C,
                      np.ascontiguousarray(pv2).reshape(-1), KERNELS[algo], s["serpentine"], s["strength"])
        idx = idx.reshape(h2, w2)
    elif algo == "threshold":
        idx = _nearest(work, pv2)
    else:
        spread = _spread(pv2.reshape(-1).tolist(), k, C)
        t = _threshold_map(algo, h2, w2, s["seed"])
        off = (t - 0.5) * s["strength"] * spread
        idx = _nearest(work + off[:, :, None], pv2)

    colors = np.array(pal, dtype=np.uint8)[idx]
    if sc > 1:
        colors = np.repeat(np.repeat(colors, sc, axis=0), sc, axis=1)[:h, :w]
    out = np.empty((h, w, 4), dtype=np.uint8)
    out[:, :, :3] = colors
    out[:, :, 3] = rgba[:, :, 3]
    return DitherResult(out, [to_hex(c) for c in pal], s, (time.perf_counter() - t0) * 1000.0)
