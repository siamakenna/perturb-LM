#!/usr/bin/env python3
"""Audit local JUMP CPJUMP1 pilot metadata and profile files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from perturb_lm.data.jump import (  # noqa: E402
    EXPECTED_BATCH,
    EXPECTED_PROFILE_KIND,
    audit_jump_pilot,
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
        help="Local JUMP pilot data root to inventory.",
    )
    parser.add_argument(
        "--expected-batch",
        default=EXPECTED_BATCH,
        help="Expected CPJUMP1 batch name used for warnings and metadata.",
    )
    parser.add_argument(
        "--expected-profile-kind",
        default=EXPECTED_PROFILE_KIND,
        help="Expected profile filename marker used to identify preferred profiles.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("outputs/jump_pilot_inventory.json"),
        help="Local JSON inventory path. Generated outputs should not be committed.",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print a concise human-readable summary instead of the full JSON payload.",
    )
    parser.add_argument(
        "--max-columns-to-print",
        type=int,
        default=None,
        help="Limit printed column previews while keeping the saved JSON inventory complete.",
    )
    args = parser.parse_args()

    inventory = audit_jump_pilot(
        args.data_root,
        expected_batch=args.expected_batch,
        expected_profile_kind=args.expected_profile_kind,
    )
    text = json.dumps(inventory, indent=2) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text)
    print(f"Wrote JUMP pilot inventory to {args.out}")
    if args.summary_only:
        print(format_audit_summary(inventory, max_columns=args.max_columns_to_print))
    else:
        printable = truncate_inventory_for_print(
            inventory,
            max_columns=args.max_columns_to_print,
        )
        print(json.dumps(printable, indent=2) + "\n")


def format_audit_summary(inventory: dict, *, max_columns: int | None = None) -> str:
    metadata_columns = _limited_list(inventory["detected_metadata_columns"], max_columns)
    feature_columns = _limited_list(inventory["detected_numeric_feature_columns"], max_columns)
    lines = [
        "JUMP pilot audit summary",
        f"Dataset: {inventory['dataset']}",
        f"Local data root: {inventory['local_data_root']}",
        f"Metadata files found: {len(inventory['metadata_files_found'])}",
        f"Profile files found: {len(inventory['profile_files_found'])}",
        f"Missing expected files: {len(inventory['missing_expected_files'])}",
        f"Metadata columns: {inventory['detected_metadata_column_count']}",
        f"Numeric feature columns: {inventory['detected_numeric_feature_column_count']}",
        f"Likely batch column: {inventory['likely_batch_column']}",
        "Inferred batches: " + ", ".join(inventory.get("inferred_batches", [])),
        f"Likely plate column: {inventory['likely_plate_column']}",
        f"Likely well column: {inventory['likely_well_column']}",
        "Likely perturbation/treatment columns: "
        + ", ".join(inventory["likely_perturbation_treatment_columns"]),
        "Metadata column preview: " + ", ".join(metadata_columns),
        "Feature column preview: " + ", ".join(feature_columns),
    ]
    if inventory["warnings"]:
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in inventory["warnings"])
    return "\n".join(lines)


def truncate_inventory_for_print(inventory: dict, *, max_columns: int | None) -> dict:
    if max_columns is None:
        return inventory
    truncated = dict(inventory)
    truncated["detected_metadata_columns"] = _limited_list(
        inventory["detected_metadata_columns"],
        max_columns,
    )
    truncated["detected_numeric_feature_columns"] = _limited_list(
        inventory["detected_numeric_feature_columns"],
        max_columns,
    )
    readable_files = []
    for summary in inventory["readable_files"]:
        truncated_summary = dict(summary)
        truncated_summary["columns"] = _limited_list(summary["columns"], max_columns)
        truncated_summary["metadata_columns"] = _limited_list(
            summary["metadata_columns"],
            max_columns,
        )
        truncated_summary["numeric_feature_columns"] = _limited_list(
            summary["numeric_feature_columns"],
            max_columns,
        )
        readable_files.append(truncated_summary)
    truncated["readable_files"] = readable_files
    return truncated


def _limited_list(values: list, max_items: int | None) -> list:
    if max_items is None or len(values) <= max_items:
        return list(values)
    remaining = len(values) - max_items
    return [*values[:max_items], f"... ({remaining} more)"]


if __name__ == "__main__":
    main()
