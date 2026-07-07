#!/usr/bin/env python3
"""Generate a Phase 2 readiness report for local RxRx assets and artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from perturb_lm.data.inventory import audit_local_dataset  # noqa: E402
from perturb_lm.reports import make_rxrx_readiness_report  # noqa: E402


def load_table(path: Path | None) -> pd.DataFrame | None:
    if path is None or not path.exists():
        return None
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def load_json(path: Path | None) -> dict[str, object] | None:
    if path is None or not path.exists():
        return None
    return json.loads(path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, choices=["rxrx1", "rxrx19a"])
    parser.add_argument("--data-root", type=Path, default=Path("data/raw"))
    parser.add_argument("--inventory", type=Path, default=None)
    parser.add_argument("--site-manifest", type=Path, default=None)
    parser.add_argument("--image-check-limit", type=int, default=200)
    parser.add_argument("--manifest-build-report", type=Path, default=None)
    parser.add_argument("--index-metadata", type=Path, default=None)
    parser.add_argument("--leakage-summary", type=Path, default=None)
    parser.add_argument("--composite-manifest", type=Path, default=None)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    site_manifest = load_table(args.site_manifest)
    inventory = load_json(args.inventory)
    if inventory is None:
        inventory = audit_local_dataset(
            args.dataset,
            args.data_root,
            site_manifest=site_manifest,
            image_check_limit=args.image_check_limit,
        ).to_dict()

    path = make_rxrx_readiness_report(
        dataset=args.dataset,
        inventory=inventory,
        manifest_build_report=load_json(args.manifest_build_report),
        index_metadata=load_json(args.index_metadata),
        leakage_summary=load_table(args.leakage_summary),
        composite_manifest=load_table(args.composite_manifest),
        out_path=args.out,
    )
    print(f"Wrote RxRx readiness report to {path}")


if __name__ == "__main__":
    main()
