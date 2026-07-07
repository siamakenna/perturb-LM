#!/usr/bin/env python3
"""Build held-out split presets for RxRx-style site manifests."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from perturb_lm.splits import (  # noqa: E402
    assign_held_out_batch_split,
    assign_held_out_image_split,
    assign_held_out_perturbation_split,
    assign_held_out_plate_split,
    assign_held_out_well_split,
)

PRESETS = {
    "held_out_well": assign_held_out_well_split,
    "held_out_image": assign_held_out_image_split,
    "held_out_plate": assign_held_out_plate_split,
    "held_out_batch": assign_held_out_batch_split,
    "held_out_perturbation": assign_held_out_perturbation_split,
}


def load_table(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def write_table(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".parquet":
        frame.to_parquet(path, index=False)
    else:
        frame.to_csv(path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--preset", choices=sorted(PRESETS), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--test-fraction", type=float, default=0.2)
    parser.add_argument("--val-fraction", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--batch-column", action="append", default=None)
    parser.add_argument("--split-column", default="split")
    args = parser.parse_args()

    manifest = load_table(args.manifest)
    kwargs = {
        "test_fraction": args.test_fraction,
        "val_fraction": args.val_fraction,
        "seed": args.seed,
        "split_column": args.split_column,
    }
    if args.preset == "held_out_batch" and args.batch_column:
        kwargs["batch_columns"] = args.batch_column
    split_manifest = PRESETS[args.preset](manifest, **kwargs)
    write_table(split_manifest, args.out)
    summary = split_manifest[args.split_column].value_counts().to_dict()
    print(f"Wrote {args.preset} manifest to {args.out}")
    print(f"Split counts: {summary}")


if __name__ == "__main__":
    main()
