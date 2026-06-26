#!/usr/bin/env python3
"""Build a local sklearn cosine index from JUMP CPJUMP1 pilot profiles."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from perturb_lm.data.jump import (  # noqa: E402
    EXPECTED_PROFILE_KIND,
    build_jump_profile_index,
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
        help="Specific profile table to index. Repeat to index multiple files.",
    )
    parser.add_argument(
        "--expected-profile-kind",
        default=EXPECTED_PROFILE_KIND,
        help="Preferred profile filename marker when auto-discovering profile files.",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional row limit for quick local checks.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("outputs/jump_pilot_index"),
        help="Local output directory for index files and metadata.",
    )
    args = parser.parse_args()

    metadata = build_jump_profile_index(
        args.data_root,
        out_dir=args.out,
        profile_files=args.profile_file,
        expected_profile_kind=args.expected_profile_kind,
        max_rows=args.max_rows,
    )
    print(f"Wrote JUMP profile index metadata to {args.out / 'index_metadata.json'}")
    print(
        "Indexed "
        f"{metadata['number_of_rows']} rows with "
        f"{metadata['number_of_numeric_feature_columns']} numeric feature columns"
    )


if __name__ == "__main__":
    main()
