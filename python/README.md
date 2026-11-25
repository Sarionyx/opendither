# OpenDither for Python

Image dithering library, command-line tool and desktop app.

```bash
pip install .            # library + CLI (numpy, Pillow)
pip install ".[fast]"    # + numba: ~100x faster error diffusion
pip install ".[gui]"     # + PySide6 desktop app (includes numba)
```

## Desktop app

```bash
opendither-gui           # or: python -m opendither
```

Open, paste (Ctrl+V) or drop an image. Tools: Hand (H), Zoom (Z), Compare (C). Hold `\` to see the
original. Drag any slider label to scrub its value, double-click it to reset. Without numba the
preview uses a smaller proxy for big images; exports are always full resolution.

## CLI

```bash
opendither photo.jpg -a atkinson -p newsprint --scale 2
opendither photo.jpg -a bayer-8 -m rgb --adaptive 8 --export-scale 4 -o big.png
opendither photos/ -o out/ --recipe my-look.json --format webp
opendither --list
```

## Library

```python
from PIL import Image
import opendither as od

res = od.dither(Image.open("photo.jpg"), {"algorithm": "stucki", "palette": "#000,#fff"}, contrast=20)
res.image          # numpy (h, w, 4) uint8
res.palette        # ['#000000', '#ffffff']
res.save("out.png", scale=2)

od.dither_file("photo.jpg", "out.png", algorithm="halftone-8", palette="riso")
```

Accepts PIL images or numpy arrays (grayscale, RGB or RGBA). Settings follow the recipe format in
[`spec/ALGORITHMS.md`](../spec/ALGORITHMS.md). `od.ENGINE` tells you whether numba is active.
