"""Synthetic-only pixel analysis demo. Does not dispatch real-data benchmarks."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from sklearn.metrics import pairwise_distances

from perturb_lm.images.pixel_analyzer import PixelMorphologyTransformer


def make_images(seed=17):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[:64, :64]
    images = []
    for i in range(12):
        channels = []
        signal = np.zeros((64, 64), float)
        radius = 3 + i % 5
        for y, x in ((16, 16), (16, 46), (46, 16), (46, 46)):
            signal += (yy - y) ** 2 + (xx - x) ** 2 <= radius**2
        for c in range(3):
            plane = ndi.gaussian_filter(signal, sigma=0.6 + c * 0.3)
            plane = 300 + (1800 + 100 * i + 50 * c) * plane
            plane += rng.normal(0, 4, plane.shape)
            channels.append(np.clip(plane, 0, 65535).astype(np.uint16))
        images.append(np.stack(channels))
    return np.stack(images)


def table(path, names, values):
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["sample_index", *names])
        for i, row in enumerate(values):
            writer.writerow([i, *row])


def object_preview(image, mask, *, channel=0):
    """Display-only overlay shared by the synthetic demo and TIFF workflow."""
    plane = image[channel].astype(float)
    lo, hi = np.quantile(plane, [0.01, 0.99])
    if hi <= lo:
        lo, hi = float(plane.min()), float(plane.max())
    view = (255 * np.clip((plane - lo) / max(hi - lo, 1e-12), 0, 1)).astype(np.uint8)
    rgb = np.repeat(view[..., None], 3, axis=2)
    boundary = (ndi.maximum_filter(mask, size=3) != ndi.minimum_filter(mask, size=3)) & (mask > 0)
    rgb[boundary] = [255, 0, 0]
    return Image.fromarray(rgb)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    images = make_images(args.seed)
    model = PixelMorphologyTransformer().fit(images[:8])
    features = model.transform(images)
    masks = np.stack([model.segment(image) for image in images])
    raw = model.raw_features(images)
    np.save(out / "synthetic_pixels.npy", images, allow_pickle=False)
    np.save(out / "object_masks.npy", masks, allow_pickle=False)
    table(out / "features.csv", model.get_feature_names_out(), features)
    table(out / "raw_features.csv", model.get_feature_names_out(), raw)
    distances = pairwise_distances(features[8:], features[:8])
    with (out / "neighbors.csv").open("x", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["query_sample_index", "rank", "candidate_sample_index", "distance"])
        for i, values in enumerate(distances):
            for rank, index in enumerate(np.argsort(values, kind="stable")[:3], 1):
                writer.writerow([i + 8, rank, int(index), float(values[index])])
    # Display only: 16-bit quantitative measurements above are not replaced.
    preview = object_preview(images[8], masks[8]).resize(
        (512, 512), resample=Image.Resampling.NEAREST
    )
    preview.save(out / "object_overlay.png")
    record = {
        "scope": "synthetic_pixel_only_demo",
        "biological_metadata_required": False,
        "model_inputs": "numeric image pixels in NCHW order",
        "shape": list(images.shape),
        "seed": args.seed,
        "n_features": int(features.shape[1]),
        "scaler_fit_sample_indices": list(range(8)),
        "held_out_query_sample_indices": list(range(8, 12)),
        "segmentation_channel": 0,
        "n_cells_claimed": False,
        "limitation": "Toy watershed objects; not biological validation.",
    }
    (out / "run.json").write_text(json.dumps(record, indent=2) + "\n")
    checksums = [
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}"
        for p in sorted(out.iterdir())
        if p.is_file()
    ]
    (out / "SHA256SUMS").write_text("\n".join(checksums) + "\n")
    print(f"PASS: pixels -> masks -> {features.shape[1]} features -> held-out image neighbors")
    print(out)


if __name__ == "__main__":
    main()
