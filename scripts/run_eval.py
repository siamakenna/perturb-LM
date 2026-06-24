#!/usr/bin/env python3
"""Evaluate Phase 1 perturbation-level retrieval results."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from perturb_lm.retrieval.metrics import evaluate_perturbation_retrieval


def load_table(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, choices=["rxrx1", "rxrx19a"])
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--site-results", type=Path, default=None)
    parser.add_argument("--perturbation-results", type=Path, required=True)
    parser.add_argument("--site-manifest", type=Path, default=None)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--top-k", type=int, nargs="+", default=[1, 5, 10])
    args = parser.parse_args()

    queries = load_table(args.queries)
    perturbation_results = load_table(args.perturbation_results)
    site_results = load_table(args.site_results) if args.site_results else None
    summary, per_query = evaluate_perturbation_retrieval(
        perturbation_results,
        queries,
        site_results=site_results,
        top_k=args.top_k,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    summary_path = args.out / "metrics_summary.csv"
    json_path = args.out / "metrics_summary.json"
    per_query_path = args.out / "per_query_metrics.csv"
    summary.to_csv(summary_path, index=False)
    per_query.to_csv(per_query_path, index=False)
    json_path.write_text(json.dumps(dict(zip(summary["metric"], summary["value"], strict=False)), indent=2) + "\n")
    print(summary.to_string(index=False))
    print(f"Wrote metrics to {summary_path}, {json_path}, and {per_query_path}")


if __name__ == "__main__":
    main()
