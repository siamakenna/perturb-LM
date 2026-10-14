#!/usr/bin/env python3
"""Create a PROPOSED_NOT_APPROVED metadata-only plate-rotation plan (#30, #52)."""

from __future__ import annotations

import argparse
import csv
import os
import subprocess
from pathlib import Path

from perturb_lm.audits.cohort import checksum, read_table, write_json
from perturb_lm.audits.rotations import NORMALIZATION_SCOPES, plan_rotations


def guarded_output(out: Path, repository: Path) -> Path:
    """Anchor to this script's repository, not the caller's current working directory."""
    repository = repository.resolve(strict=True)
    root = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if Path(root).resolve() != repository:
        raise ValueError("Script repository root does not match Git root")
    out = out.resolve()
    if not out.is_relative_to(repository / "outputs") or out.exists():
        raise ValueError("Choose a new directory inside this repository's ignored outputs/")
    for name in ("rotation-plan.json", "rotation-manifest_PRIVATE.csv", "SHA256SUMS"):
        result = subprocess.run(
            ["git", "-C", str(repository), "check-ignore", "--quiet", str(out / name)],
            check=False,
            capture_output=True,
        )
        if result.returncode != 0:
            raise ValueError("Every output must be Git-ignored")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--mapping", type=Path, help="Existing local_mapping_PRIVATE.csv")
    source.add_argument(
        "--synthetic-fixture", action="store_true", help="Use the tracked synthetic fixture only"
    )
    parser.add_argument(
        "--out", required=True, type=Path, help="New ignored directory under outputs/"
    )
    parser.add_argument("--min-train-groups", required=True, type=int)
    parser.add_argument("--min-evaluable-groups", required=True, type=int)
    parser.add_argument(
        "--upstream-normalization-scope", required=True, choices=NORMALIZATION_SCOPES
    )
    parser.add_argument(
        "--split-policy",
        default="seen_treatment",
        choices=("seen_treatment", "heldout_treatment", "heldout_gene"),
    )
    args = parser.parse_args()
    os.umask(0o077)
    repository = Path(__file__).resolve().parents[1]
    out = guarded_output(args.out, repository)
    mapping = (
        repository / "tests/fixtures/phase5_1/rotation_mapping_synthetic.csv"
        if args.synthetic_fixture
        else args.mapping
    ).resolve(strict=True)
    if not mapping.is_file():
        raise ValueError("Mapping must be an existing CSV file")
    with mapping.open(newline="") as stream:
        columns = next(csv.reader(stream), [])
    if len(columns) != len(set(columns)):
        raise ValueError("Duplicate input CSV column names")
    before = checksum(mapping)
    summary, manifest = plan_rotations(
        read_table(mapping),
        min_train_groups=args.min_train_groups,
        min_evaluable_groups=args.min_evaluable_groups,
        upstream_normalization_scope=args.upstream_normalization_scope,
        split_policy=args.split_policy,
    )
    if checksum(mapping) != before:
        raise ValueError("Mapping changed during planning")
    summary["evidence_kind"] = (
        "synthetic_fixture" if args.synthetic_fixture else "operator_supplied_mapping"
    )
    summary["input_mapping_sha256"] = before
    summary["source_git_sha"] = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    summary["implementation_sha256"] = {
        "script": checksum(Path(__file__)),
        "module": checksum(repository / "src/perturb_lm/audits/rotations.py"),
    }
    out.mkdir(parents=True, exist_ok=False)
    manifest.to_csv(out / "rotation-manifest_PRIVATE.csv", index=False, lineterminator="\n")
    write_json(out / "rotation-plan.json", summary)
    files = [out / "rotation-plan.json", out / "rotation-manifest_PRIVATE.csv"]
    (out / "SHA256SUMS").write_text("".join(f"{checksum(path)}  {path.name}\n" for path in files))
    print(
        "PROPOSED_NOT_APPROVED: 12 candidate rotations, "
        f"{summary['design_eligible_rotations']} structurally eligible; execution_allowed=false"
    )
    print("No fitting, scores, or inference performed. Outputs remain private under outputs/.")


if __name__ == "__main__":
    main()
