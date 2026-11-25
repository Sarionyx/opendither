"""Procedural sample image (no bundled assets needed)."""
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def _ramp(t, stops):
    t = np.clip(t, 0, 1)
    out = np.zeros(t.shape + (3,))
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        m = (t >= t0) & (t <= t1)
        k = ((t - t0) / (t1 - t0))[..., None]
        out[m] = (np.array(c0) * (1 - k) + np.array(c1) * k)[m]
    return out


def make_sample(W=960, H=640):
    y, x = np.mgrid[0:H, 0:W].astype(np.float64)
    img = _ramp(y / (H - 1), [(0, (29, 43, 100)), (0.55, (192, 88, 126)), (1, (248, 178, 106))])

    d = np.hypot(x - 640, y - 330) / 170
    glow = np.clip(1 - d, 0, 1)[..., None]
    sun = _ramp(d, [(0, (255, 247, 214)), (0.35, (255, 210, 122)), (1, (255, 190, 110))])
    img = img * (1 - glow) + sun * glow

    for i, (col, base, amp, freq) in enumerate([((59, 36, 88), 380, 70, 0.006), ((42, 26, 64), 440, 60, 0.011),
                                                ((22, 15, 36), 520, 45, 0.018)]):
        xs = np.arange(W)
        ridge = base + np.sin(xs * freq + i * 2) * amp + np.sin(xs * freq * 3.1 + i) * amp * 0.35
        img[y > ridge[None, :]] = col

    cx, cy, r = 240, 250, 110
    inside = np.hypot(x - cx, y - cy) <= r
    lt = np.hypot(x - 205, y - 215) / 230
    ball = _ramp(lt, [(0, (255, 255, 255)), (0.3, (143, 211, 255)), (1, (11, 42, 91))])
    img[inside] = ball[inside]

    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB")
    draw = ImageDraw.Draw(im)
    font = None
    for name in ("segoeuib.ttf", "Arial Bold.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            font = ImageFont.truetype(name, 64)
            break
        except OSError:
            continue
    font = font or ImageFont.load_default()
    draw.text((W / 2, 600), "OpenDither", fill=(255, 255, 255), font=font, anchor="ms")
    return im
