"""Command line interface: `opendither photo.jpg -a atkinson -p newsprint --scale 2`."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import ALGORITHMS, DEFAULTS, ENGINE, PALETTES, __version__, dither

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}


def build_parser():
    p = argparse.ArgumentParser(
        prog="opendither",
        description="Dither images from the command line. Settings mirror the OpenDither recipe format.",
        epilog="Examples:\n"
               "  opendither photo.jpg -a atkinson -p newsprint --scale 2\n"
               "  opendither photos/ -o out/ --recipe my-look.json\n"
               "  opendither photo.jpg -a bayer-8 --color-mode rgb --adaptive 8 --export-scale 4\n"
               "  opendither --list",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("inputs", nargs="*", help="image files or folders")
    p.add_argument("-o", "--output", help="output file (single input) or folder")
    p.add_argument("-r", "--recipe", help="JSON recipe file (from the web or desktop app)")
    p.add_argument("-a", "--algorithm", help="dithering algorithm (see --list)")
    p.add_argument("-p", "--palette", help="preset id or colors, e.g. '#000,#fff'")
    p.add_argument("-m", "--color-mode", choices=["luminance", "rgb"])
    p.add_argument("-s", "--scale", type=int, help="pixel size (1-64)")
    p.add_argument("--strength", type=float, help="diffusion / spread amount, 0-2 (1 = 100%%)")
    p.add_argument("--no-serpentine", action="store_true", help="scan every row left to right")
    p.add_argument("--seed", type=int, help="seed for the random algorithm")
    p.add_argument("--brightness", type=float)
    p.add_argument("--contrast", type=float)
    p.add_argument("--saturation", type=float)
    p.add_argument("--gamma", type=float)
    p.add_argument("--invert", action="store_true")
    p.add_argument("--adaptive", type=int, help="build an N-color palette from the image")
    p.add_argument("--export-scale", type=int, default=1, help="upscale the output N times (nearest neighbour)")
    p.add_argument("--format", default="png", help="output format when writing to a folder (png, webp, jpg...)")
    p.add_argument("--save-recipe", help="write the effective recipe to this JSON file")
    p.add_argument("--list", action="store_true", help="list algorithms and palettes")
    p.add_argument("--version", action="version", version=f"opendither {__version__} (engine: {ENGINE})")
    return p


def recipe_from_args(a):
    s = dict(DEFAULTS)
    if a.recipe:
        s.update(json.loads(Path(a.recipe).read_text(encoding="utf-8")))
    for key, val in (("algorithm", a.algorithm), ("palette", a.palette), ("colorMode", a.color_mode),
                     ("scale", a.scale), ("strength", a.strength), ("seed", a.seed),
                     ("brightness", a.brightness), ("contrast", a.contrast), ("saturation", a.saturation),
                     ("gamma", a.gamma), ("adaptive", a.adaptive)):
        if val is not None:
            s[key] = val
    if a.no_serpentine:
        s["serpentine"] = False
    if a.invert:
        s["invert"] = True
    return s


def collect(inputs):
    files = []
    for item in inputs:
        path = Path(item)
        if path.is_dir():
            files += sorted(f for f in path.iterdir() if f.suffix.lower() in IMAGE_EXT)
        elif path.exists():
            files.append(path)
        else:
            raise SystemExit(f"opendither: no such file: {item}")
    return files


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")  # names like "Floyd–Steinberg" on legacy consoles
    a = build_parser().parse_args(argv)
    if a.list:
        print("Algorithms:")
        group = None
        for al in ALGORITHMS:
            if al["group"] != group:
                group = al["group"]
                print(f"  {group}")
            print(f"    {al['id']:<24}{al['name']}")
        print("\nPalettes:")
        for p in PALETTES:
            print(f"    {p['id']:<24}{p['name']} ({len(p['colors'])})")
        return 0
    if not a.inputs:
        build_parser().print_help()
        return 1

    from PIL import Image

    recipe = recipe_from_args(a)
    files = collect(a.inputs)
    if not files:
        raise SystemExit("opendither: no images found")
    single = len(files) == 1 and not (a.output and Path(a.output).is_dir())
    out_dir = None if single else Path(a.output or ".")
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    for f in files:
        if single:
            dst = Path(a.output) if a.output else f.with_name(f.stem + "-dithered.png")
        else:
            dst = out_dir / f"{f.stem}-dithered.{a.format.lstrip('.')}"
        with Image.open(f) as im:
            res = dither(im, recipe)
        res.save(dst, scale=a.export_scale)
        print(f"{f} -> {dst}  ({res.width}x{res.height}, {len(res.palette)} colors, {res.ms:.0f} ms)")

    if a.save_recipe:
        Path(a.save_recipe).write_text(json.dumps(res.settings, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
