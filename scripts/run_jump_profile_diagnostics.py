#!/usr/bin/env python3
"""Run leakage-aware nearest-neighbor diagnostics for JUMP CPJUMP1 profiles."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from perturb_lm.data.jump import (  # noqa: E402
    EXPECTED_PROFILE_KIND,
    run_jump_profile_diagnostics,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path("data/raw/jump_pilot"),
        help="Local JUMP pilot data root to scan for profile tables.",
    )
    parser.add_argument(
        "--profile-file",
        type=Path,
        action="append",
        default=None,
        help="Specific profile table to diagnose. Repeat to combine multiple files.",
    )
    parser.add_argument(
        "--expected-profile-kind",
        default=EXPECTED_PROFILE_KIND,
        help="Preferred profile filename marker when auto-discovering profile files.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        nargs="+",
        default=[1, 5, 10],
        help="One or more K values for nearest-neighbor diagnostics.",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional row limit for quick local checks.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Random seed for random and shuffled-label controls.",
    )
    parser.add_argument(
        "--exclude-same-plate",
        action="store_true",
        help="Add a filtered same-treatment diagnostic excluding same-plate neighbors.",
    )
    parser.add_argument(
        "--exclude-same-well",
        action="store_true",
        help="Add a filtered same-treatment diagnostic excluding same-well neighbors.",
    )
    parser.add_argument(
        "--exclude-same-batch",
        action="store_true",
        help="Add a filtered same-treatment diagnostic excluding same-batch neighbors.",
    )
    parser.add_argument(
        "--filtered-presets",
        action="store_true",
        help="Also run exclude_same_plate, exclude_same_well, and exclude_same_plate_and_well.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("outputs/jump_pilot_diagnostics"),
        help="Local output directory for diagnostics CSV/JSON files.",
    )
    args = parser.parse_args()

    per_query, summary, metadata = run_jump_profile_diagnostics(
        args.data_root,
        profile_files=args.profile_file,
        expected_profile_kind=args.expected_profile_kind,
        top_k=args.top_k,
        max_rows=args.max_rows,
        seed=args.seed,
        exclude_same_plate=args.exclude_same_plate,
        exclude_same_well=args.exclude_same_well,
        exclude_same_batch=args.exclude_same_batch,
        filtered_presets=args.filtered_presets,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    per_query_path = args.out / "profile_neighbor_diagnostics.csv"
    summary_path = args.out / "profile_neighbor_diagnostics_summary.csv"
    metadata_path = args.out / "profile_neighbor_diagnostics_summary.json"
    per_query.to_csv(per_query_path, index=False)
    summary.to_csv(summary_path, index=False)
    metadata_path.write_text(
        json.dumps(
            {
                "metadata": metadata,
                "summary": summary.to_dict(orient="records"),
            },
            indent=2,
        )
        + "\n"
    )
    print(f"Wrote per-query diagnostics to {per_query_path}")
    print(f"Wrote diagnostics summary to {summary_path} and {metadata_path}")


if __name__ == "__main__":
    main()
