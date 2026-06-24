#!/usr/bin/env python3
"""Render local microscopy channel images into RGB composites."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from perturb_lm.images.composite import render_manifest_composites


def load_table(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def parse_size(value: str | None) -> tuple[int, int] | None:
    if value is None:
        return None
    if "x" not in value.lower():
        raise argparse.ArgumentTypeError("Size must look like WIDTHxHEIGHT, for example 224x224.")
    width, height = value.lower().split("x", 1)
    return int(width), int(height)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-manifest", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, default=None)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--size", type=parse_size, default="224x224")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    site_manifest = load_table(args.site_manifest)
    composite_manifest = render_manifest_composites(
        site_manifest,
        args.out / "images",
        raw_root=args.raw_root,
        limit=args.limit,
        output_size=args.size,
        overwrite=args.overwrite,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "composite_manifest.csv"
    composite_manifest.to_csv(path, index=False)
    rendered = int((composite_manifest["composite_status"] == "rendered").sum())
    existing = int((composite_manifest["composite_status"] == "exists").sum())
    missing = int((composite_manifest["composite_status"] == "missing_channels").sum())
    print(f"Wrote composite manifest: {path}")
    print(f"Rendered: {rendered}; already existed: {existing}; missing channels: {missing}")


if __name__ == "__main__":
    main()
