#!/usr/bin/env python3
"""Check whether local Phase 2 JUMP artifacts are ready for Phase 3 review."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

REQUIRED_ARTIFACTS = {
    "inventory": "inventory.json",
    "baseline_manifest": "baseline_manifest.json",
    "index_metadata": "index/index_metadata.json",
    "diagnostics_summary": "diagnostics/profile_neighbor_diagnostics_summary.csv",
    "diagnostics_json": "diagnostics/profile_neighbor_diagnostics_summary.json",
    "text_profile_summary": "text_profile/jump_text_profile_summary.csv",
    "text_profile_metadata": "text_profile/jump_text_profile_metadata.json",
    "report": "phase2_jump_report.md",
}


def check_phase2_readiness(root: Path | str) -> dict[str, Any]:
    """Return pass/fail checks for the generated Phase 2 local baseline directory."""

    root = Path(root)
    checks: list[dict[str, Any]] = []
    loaded: dict[str, Any] = {}
    for name, relative_path in REQUIRED_ARTIFACTS.items():
        path = root / relative_path
        ok = path.exists()
        checks.append(
            {
                "check": f"artifact:{name}",
                "status": "pass" if ok else "fail",
                "detail": str(path),
            }
        )
        if ok:
            loaded[name] = _load_artifact(path)

    manifest = loaded.get("baseline_manifest", {})
    checks.extend(_manifest_checks(manifest))
    diagnostics = loaded.get("diagnostics_summary")
    if isinstance(diagnostics, pd.DataFrame):
        checks.extend(_diagnostic_checks(diagnostics))
    text_summary = loaded.get("text_profile_summary")
    if isinstance(text_summary, pd.DataFrame):
        checks.extend(_text_profile_checks(text_summary))

    failed = [row for row in checks if row["status"] == "fail"]
    warnings = [row for row in checks if row["status"] == "warn"]
    return {
        "root": str(root),
        "ready_for_phase3": not failed,
        "n_checks": len(checks),
        "n_failed": len(failed),
        "n_warnings": len(warnings),
        "checks": checks,
        "interpretation": (
            "Ready means reproducibility artifacts and controls are present. It does "
            "not mean biological retrieval has been demonstrated."
        ),
    }


def _load_artifact(path: Path) -> Any:
    if path.suffix == ".json":
        return json.loads(path.read_text())
    if path.suffix == ".csv":
        return pd.read_csv(path)
    return path.read_text(errors="ignore")


def _manifest_checks(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    if not manifest:
        return []
    checks = [
        _check(
            "manifest:profile_rows",
            int(manifest.get("indexed_profile_rows") or 0) > 0,
            f"indexed_profile_rows={manifest.get('indexed_profile_rows')}",
        ),
        _check(
            "manifest:text_profile_modes",
            {"metadata_tfidf", "identifier_stripped_tfidf", "random", "shuffled_label"}.issubset(
                set(manifest.get("text_profile_modes", []))
            ),
            f"modes={manifest.get('text_profile_modes')}",
        ),
        _check(
            "manifest:label_columns",
            bool(manifest.get("batch_column"))
            and bool(manifest.get("plate_column"))
            and bool(manifest.get("well_column"))
            and bool(manifest.get("treatment_columns")),
            (
                f"batch={manifest.get('batch_column')}; plate={manifest.get('plate_column')}; "
                f"well={manifest.get('well_column')}; treatment={manifest.get('treatment_columns')}"
            ),
        ),
    ]
    if manifest.get("batch_column") == "Metadata_Inferred_Batch":
        checks.append(
            {
                "check": "manifest:batch_generalization",
                "status": "warn",
                "detail": (
                    "Batch was inferred from paths; verify more than one batch before "
                    "Phase 3."
                ),
            }
        )
    return checks


def _diagnostic_checks(summary: pd.DataFrame) -> list[dict[str, Any]]:
    metrics = set(summary.get("metric", pd.Series(dtype=str)).astype(str))
    filters = set(summary.get("filter_name", pd.Series(dtype=str)).astype(str))
    return [
        _check(
            "diagnostics:controls",
            "random_same_perturbation_treatment_at_1" in metrics
            and "shuffled_same_perturbation_treatment_at_1" in metrics,
            "random and shuffled same-treatment controls at K=1",
        ),
        _check(
            "diagnostics:filtered_presets",
            {
                "unfiltered",
                "exclude_same_plate",
                "exclude_same_well",
                "exclude_same_plate_and_well",
            }.issubset(filters),
            f"filters={sorted(filters)}",
        ),
    ]


def _text_profile_checks(summary: pd.DataFrame) -> list[dict[str, Any]]:
    modes = set(summary.get("mode", pd.Series(dtype=str)).astype(str))
    metrics = set(summary.get("metric", pd.Series(dtype=str)).astype(str))
    return [
        _check(
            "text_profile:required_modes",
            {"metadata_tfidf", "identifier_stripped_tfidf", "random", "shuffled_label"}.issubset(
                modes
            ),
            f"modes={sorted(modes)}",
        ),
        _check(
            "text_profile:required_metrics",
            {
                "mean_average_precision",
                "mean_hit_at_1",
                "queries_with_positive_cross_plate",
            }.issubset(metrics),
            f"metrics={sorted(metrics)}",
        ),
    ]


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"check": name, "status": "pass" if ok else "fail", "detail": detail}


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--root", type=Path, default=Path("outputs/jump_pilot_real_baseline"))
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    result = check_phase2_readiness(args.root)
    text = json.dumps(result, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
        print(f"Wrote Phase 2 readiness check to {args.out}")
    print(text)
    if not result["ready_for_phase3"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
