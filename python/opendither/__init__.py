"""OpenDither — open-source image dithering.

    >>> from opendither import dither
    >>> from PIL import Image
    >>> result = dither(Image.open("photo.jpg"), algorithm="atkinson", palette="newsprint", scale=2)
    >>> result.save("photo-dithered.png")
"""
from .core import (
    ALGORITHMS,
    DEFAULTS,
    ENGINE,
    KERNELS,
    DitherResult,
    dither,
    get_matrix,
    lowbias32,
    median_cut,
    normalize_settings,
    parse_color,
    resolve_palette,
    to_hex,
)
from .palettes import PALETTES, find_palette

__version__ = "1.0.0"


def dither_file(src, dst=None, settings=None, export_scale=1, **kw):
    """Dither an image file and save it. Returns the output path."""
    from pathlib import Path

    from PIL import Image

    src = Path(src)
    dst = Path(dst) if dst else src.with_name(src.stem + "-dithered.png")
    with Image.open(src) as im:
        dither(im, settings, **kw).save(dst, scale=export_scale)
    return dst


__all__ = [
    "ALGORITHMS", "DEFAULTS", "ENGINE", "KERNELS", "PALETTES", "DitherResult", "dither", "dither_file",
    "find_palette", "get_matrix", "lowbias32", "median_cut", "normalize_settings", "parse_color",
    "resolve_palette", "to_hex", "__version__",
]
