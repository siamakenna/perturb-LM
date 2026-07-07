#!/usr/bin/env python3
"""Generate a Phase 2 JUMP profile report from local baseline artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from perturb_lm.reports import make_phase2_jump_report  # noqa: E402


def load_json(path: Path | None) -> dict[str, object]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text())


def load_diagnostics_metadata(path: Path | None) -> dict[str, object]:
    payload = load_json(path)
    metadata = payload.get("metadata", {})
    return metadata if isinstance(metadata, dict) else {}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path("outputs/jump_pilot_inventory.json"),
        help="Inventory JSON written by scripts/audit_jump_pilot.py.",
    )
    parser.add_argument(
        "--index-metadata",
        type=Path,
        default=Path("outputs/jump_pilot_index/index_metadata.json"),
        help="Index metadata JSON written by scripts/build_jump_profile_index.py.",
    )
    parser.add_argument(
        "--diagnostics-summary",
        type=Path,
        default=Path("outputs/jump_profile_diagnostics/profile_neighbor_diagnostics_summary.csv"),
        help="Summary CSV written by scripts/run_jump_profile_diagnostics.py.",
    )
    parser.add_argument(
        "--diagnostics-json",
        type=Path,
        default=None,
        help="Optional diagnostics summary JSON for warnings and run metadata.",
    )
    parser.add_argument(
        "--text-profile-summary",
        type=Path,
        default=None,
        help="Optional summary CSV from scripts/run_jump_text_profile_retrieval.py.",
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    diagnostics_summary = pd.read_csv(args.diagnostics_summary)
    text_profile_summary = (
        pd.read_csv(args.text_profile_summary) if args.text_profile_summary else None
    )
    path = make_phase2_jump_report(
        inventory=load_json(args.inventory),
        index_metadata=load_json(args.index_metadata),
        diagnostics_summary=diagnostics_summary,
        diagnostics_metadata=load_diagnostics_metadata(args.diagnostics_json),
        text_profile_summary=text_profile_summary,
        out_path=args.out,
    )
    print(f"Wrote Phase 2 JUMP profile report to {path}")


if __name__ == "__main__":
    main()
