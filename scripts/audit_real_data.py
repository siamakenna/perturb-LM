#!/usr/bin/env python3
"""Audit local real RxRx metadata, embeddings, and image availability."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from perturb_lm.data.inventory import audit_local_dataset


def load_table(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, choices=["rxrx1", "rxrx19a"])
    parser.add_argument("--data-root", type=Path, default=Path("data/raw"))
    parser.add_argument("--site-manifest", type=Path, default=None)
    parser.add_argument("--image-check-limit", type=int, default=200)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    site_manifest = load_table(args.site_manifest) if args.site_manifest else None
    inventory = audit_local_dataset(
        args.dataset,
        args.data_root,
        site_manifest=site_manifest,
        image_check_limit=args.image_check_limit,
    )
    payload = inventory.to_dict()
    text = json.dumps(payload, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
        print(f"Wrote real-data inventory to {args.out}")
    print(text)


if __name__ == "__main__":
    main()
