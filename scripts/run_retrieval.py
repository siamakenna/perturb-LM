#!/usr/bin/env python3
"""Run Phase 1 text-to-image retrieval modes."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from perturb_lm.retrieval.search import run_retrieval, write_retrieval_outputs


def load_table(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, choices=["rxrx1", "rxrx19a"])
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--site-manifest", type=Path, required=True)
    parser.add_argument("--mode", choices=["lexical", "random", "shuffled", "embedding"], default="lexical")
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--index", type=Path, default=None)
    parser.add_argument("--text-embedding-mode", default="hashing")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    queries = load_table(args.queries)
    site_manifest = load_table(args.site_manifest)
    site_results, perturbation_results = run_retrieval(
        queries,
        site_manifest,
        dataset=args.dataset,
        mode=args.mode,
        top_k=args.top_k,
        seed=args.seed,
        index_dir=args.index,
        text_embedding_mode=args.text_embedding_mode,
    )
    paths = write_retrieval_outputs(args.dataset, site_results, perturbation_results, args.out)
    print(f"Wrote {len(site_results)} site-level rows to {paths['site_csv']} and {paths['site_parquet']}")
    print(
        "Wrote "
        f"{len(perturbation_results)} perturbation-level rows to "
        f"{paths['perturbation_csv']} and {paths['perturbation_parquet']}"
    )


if __name__ == "__main__":
    main()
