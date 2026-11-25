import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

import opendither as od

SPEC = Path(__file__).resolve().parents[2] / "spec"
VECTORS = json.loads((SPEC / "test-vectors.json").read_text(encoding="utf-8"))


def make_test_image(w, h):
    y, x = np.mgrid[0:h, 0:w]
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[:, :, 0] = (x * 255) // (w - 1)
    img[:, :, 1] = (y * 255) // (h - 1)
    img[:, :, 2] = (x * x + 3 * x * y) % 256
    img[:, :, 3] = 255 - ((x * y) % 64)
    return img


IMG = make_test_image(VECTORS["width"], VECTORS["height"])


@pytest.mark.parametrize("case", VECTORS["cases"], ids=lambda c: json.dumps(c["settings"]))
def test_matches_reference_vectors(case):
    res = od.dither(IMG, case["settings"])
    assert hashlib.sha256(res.image.tobytes()).hexdigest() == case["sha256"]


def test_palettes_match_spec():
    spec = json.loads((SPEC / "palettes.json").read_text(encoding="utf-8"))
    assert spec == od.PALETTES


def test_algorithm_ids_cover_spec():
    ids = {a["id"] for a in od.ALGORITHMS}
    assert set(od.KERNELS) <= ids
    assert len(ids) == 21


def test_only_palette_colors_and_mid_gray():
    flat = np.full((64, 64, 3), 128, np.uint8)
    for a in od.ALGORITHMS:
        out = od.dither(flat, algorithm=a["id"]).image
        assert set(np.unique(out[:, :, 0])) <= {0, 255}, a["id"]
        if a["id"] != "threshold":
            assert abs(out[:, :, 0].mean() - 128) < 20, a["id"]


def test_inputs_and_scale():
    from PIL import Image

    gray = np.linspace(0, 255, 70 * 33).reshape(33, 70).astype(np.uint8)
    res = od.dither(gray, scale=4, algorithm="bayer-4")
    assert res.image.shape == (33, 70, 4)
    res2 = od.dither(Image.fromarray(gray), scale=4, algorithm="bayer-4")
    assert np.array_equal(res.image, res2.image)


def test_recipe_normalization():
    s = od.normalize_settings({"scale": "3.7", "strength": 9, "adaptive": 1, "invert": "false", "algorithm": "nope"})
    assert s["scale"] == 3 and s["strength"] == 2 and s["adaptive"] == 0
    assert s["invert"] is False and s["algorithm"] == "floyd-steinberg"
    assert od.resolve_palette("#000, #fff") == [(0, 0, 0), (255, 255, 255)]
    assert od.parse_color("#fa0") == (255, 170, 0)
