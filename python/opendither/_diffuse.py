"""Error-diffusion inner loop.

The loop is inherently sequential, so it is compiled with numba when available (~100x faster).
Without numba the same code runs as plain Python on lists. Set OPENDITHER_NO_NUMBA=1 to force
the pure-Python path.
"""
import math
import os

import numpy as np


def _diffuse_impl(buf, w, h, C, pv, k, dxs, dys, cfs, ne, serpentine, strength, out, e):
    for y in range(h):
        rev = serpentine and (y % 2 == 1)
        for i in range(w):
            x = w - 1 - i if rev else i
            o = (y * w + x) * C
            best = 0
            bestd = math.inf
            for p in range(k):
                d = 0.0
                for c in range(C):
                    dd = buf[o + c] - pv[p * C + c]
                    d += dd * dd
                if d < bestd:
                    bestd = d
                    best = p
            out[y * w + x] = best
            for c in range(C):
                e[c] = (buf[o + c] - pv[best * C + c]) * strength
            for q in range(ne):
                nx = x - dxs[q] if rev else x + dxs[q]
                ny = y + dys[q]
                if nx < 0 or nx >= w or ny >= h:
                    continue
                no = (ny * w + nx) * C
                co = cfs[q]
                for c in range(C):
                    buf[no + c] += e[c] * co


ENGINE = "python"
_fast = None
if os.environ.get("OPENDITHER_NO_NUMBA", "") not in ("1", "true", "yes"):
    try:
        from numba import njit

        _fast = njit(cache=True, nogil=True)(_diffuse_impl)
        ENGINE = "numba"
    except Exception:  # numba missing or broken: fall back silently
        _fast = None


def diffuse(work, w, h, C, pv, kernel, serpentine, strength):
    """Run error diffusion. `work` is a flat float64 array (modified), `pv` a flat palette array.
    Returns a flat int array of palette indices."""
    divisor, entries = kernel
    dxs = np.array([e[0] for e in entries], dtype=np.int64)
    dys = np.array([e[1] for e in entries], dtype=np.int64)
    cfs = np.array([e[2] / divisor for e in entries], dtype=np.float64)
    k = len(pv) // C
    if _fast is not None:
        out = np.zeros(w * h, dtype=np.int64)
        _fast(work, w, h, C, pv, k, dxs, dys, cfs, len(entries), bool(serpentine), float(strength), out, np.zeros(C))
        return out
    out = [0] * (w * h)
    _diffuse_impl(work.tolist(), w, h, C, pv.tolist(), k, dxs.tolist(), dys.tolist(), cfs.tolist(),
                  len(entries), bool(serpentine), float(strength), out, [0.0] * C)
    return np.array(out, dtype=np.int64)
