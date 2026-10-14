#!/usr/bin/env python3
"""Audit source metadata and optionally local historical profiles; never run inference."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from perturb_lm.audits.cohort import cohort_audit, fetch_source


def ignored_output(path: Path) -> Path:
    path = path.resolve()
    result = subprocess.run(
        ["git", "check-ignore", "--quiet", str(path / "audit.json")],
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise ValueError("Output must be in a Git-ignored directory, normally outputs/phase5")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, help="Existing local jump_pilot directory")
    parser.add_argument("--source-root", type=Path, default=Path("outputs/phase5/source"))
    parser.add_argument("--out", type=Path, default=Path("outputs/phase5/cohort"))
    parser.add_argument(
        "--fetch-source", action="store_true", help="Fetch fixed small public metadata"
    )
    parser.add_argument(
        "--profile-diagnostics", action="store_true", help="Descriptive cosine only"
    )
    args = parser.parse_args()
    out = ignored_output(args.out)
    if args.fetch_source:
        fetch_source(ignored_output(args.source_root))
    summary = cohort_audit(args.data_root, args.source_root, out, features=args.profile_diagnostics)
    print(
        f"Source plates: {summary['source_plate_count']}; local status: {summary['local_status']}"
    )
    print(
        f"Local rows: {summary.get('local_rows', 0)}; "
        f"unresolved: {summary.get('unresolved_rows', 0)}"
    )


if __name__ == "__main__":
    main()
