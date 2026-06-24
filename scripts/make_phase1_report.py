#!/usr/bin/env python3
"""Generate a Markdown report from Phase 1 outputs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from perturb_lm.reports import make_phase1_report


def load_table(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, choices=["rxrx1", "rxrx19a"])
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--site-manifest", type=Path, required=True)
    parser.add_argument("--perturbation-results", type=Path, required=True)
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--mode", default="unknown")
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    path = make_phase1_report(
        dataset=args.dataset,
        queries=load_table(args.queries),
        site_manifest=load_table(args.site_manifest),
        perturbation_results=load_table(args.perturbation_results),
        metrics=load_table(args.metrics),
        out_path=args.out / "phase1_report.md" if args.out.suffix == "" else args.out,
        mode=args.mode,
        fixture=args.fixture,
    )
    print(f"Wrote Phase 1 report to {path}")


if __name__ == "__main__":
    main()
