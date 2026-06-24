#!/usr/bin/env python3
"""Build a simple sklearn cosine nearest-neighbor index for site embeddings."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from perturb_lm.retrieval.embeddings import load_site_embeddings
from perturb_lm.retrieval.index import save_sklearn_index


def load_table(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, choices=["rxrx1", "rxrx19a"])
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--embeddings", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--id-column", default="site_id")
    args = parser.parse_args()

    manifest = load_table(args.manifest)
    result = load_site_embeddings(args.embeddings, manifest, id_column=args.id_column)
    saved = save_sklearn_index(result, args.out, dataset=args.dataset, id_column=args.id_column)
    print(f"Loaded {result.n_embeddings} embeddings with dimension {result.dimension}")
    print(f"Matched {result.matched} embeddings to manifest; unmatched embeddings: {result.unmatched}")
    print(f"Wrote index metadata to {saved.metadata_path}")


if __name__ == "__main__":
    main()
