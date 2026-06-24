#!/usr/bin/env python3
"""Build natural-language query tables from perturbation manifests."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from perturb_lm.queries.build_queries import build_queries, load_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, choices=["rxrx1", "rxrx19a"])
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("data/processed"))
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    queries = build_queries(args.dataset, manifest)
    args.out.mkdir(parents=True, exist_ok=True)
    out_path = args.out / f"{args.dataset}_queries.csv"
    legacy_path = args.out / "queries.csv"
    queries.to_csv(out_path, index=False)
    queries.to_csv(legacy_path, index=False)
    print(f"Wrote {len(queries)} queries to {out_path}")


if __name__ == "__main__":
    main()
