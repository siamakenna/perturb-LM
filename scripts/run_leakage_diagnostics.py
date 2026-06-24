#!/usr/bin/env python3
"""Run Phase 1 query-positive leakage diagnostics."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from perturb_lm.diagnostics import query_positive_leakage_diagnostics, summarize_leakage_diagnostics


def load_table(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--site-manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    queries = load_table(args.queries)
    site_manifest = load_table(args.site_manifest)
    diagnostics = query_positive_leakage_diagnostics(queries, site_manifest)
    summary = summarize_leakage_diagnostics(diagnostics)

    diagnostics_path = args.out / "query_positive_leakage_diagnostics.csv"
    summary_csv = args.out / "leakage_summary.csv"
    summary_json = args.out / "leakage_summary.json"
    diagnostics.to_csv(diagnostics_path, index=False)
    summary.to_csv(summary_csv, index=False)
    summary_json.write_text(json.dumps(dict(zip(summary["metric"], summary["value"], strict=False)), indent=2) + "\n")

    print(f"Wrote query leakage diagnostics to {diagnostics_path}")
    print(f"Wrote leakage summary to {summary_csv} and {summary_json}")


if __name__ == "__main__":
    main()
