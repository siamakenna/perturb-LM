#!/usr/bin/env python3
"""Run a synthetic Phase 2 JUMP pipeline smoke workflow."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from perturb_lm.data.jump import (  # noqa: E402
    EXPECTED_BATCH,
    EXPECTED_METADATA_FILES,
    EXPECTED_PROFILE_KIND,
    audit_jump_pilot,
    build_jump_profile_index,
    run_jump_profile_diagnostics,
)
from perturb_lm.reports import make_phase2_jump_report  # noqa: E402


def write_synthetic_jump_pilot(data_root: Path) -> Path:
    """Write tiny JUMP pilot-like metadata and profile tables."""

    metadata_dir = data_root / "metadata"
    profile_dir = data_root / "profiles" / EXPECTED_BATCH / "BR001"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    profile_dir.mkdir(parents=True, exist_ok=True)

    metadata_payloads = {
        "experiment-metadata.tsv": pd.DataFrame(
            {
                "Metadata_Batch": [EXPECTED_BATCH],
                "Metadata_Profile_Kind": [EXPECTED_PROFILE_KIND],
                "Metadata_Source": ["synthetic smoke"],
            }
        ),
        "JUMP-Target-1_compound_metadata.tsv": pd.DataFrame(
            {
                "Metadata_broad_sample": ["BRD-A", "BRD-B"],
                "Metadata_pert_iname": ["compound-a", "compound-b"],
            }
        ),
        "JUMP-Target-1_compound_metadata_targets.tsv": pd.DataFrame(
            {
                "pert_iname": ["compound-a", "compound-b"],
                "target": ["GENE_A", "GENE_B"],
            }
        ),
        "JUMP-Target-1_crispr_metadata.tsv": pd.DataFrame(
            {"Metadata_gene": ["GENE_A", "GENE_B"]}
        ),
        "JUMP-Target-1_orf_metadata.tsv": pd.DataFrame(
            {"Metadata_gene": ["GENE_A", "GENE_B"]}
        ),
    }
    for expected_name in EXPECTED_METADATA_FILES:
        frame = metadata_payloads[expected_name]
        frame.to_csv(metadata_dir / expected_name, sep="\t", index=False)

    profile_path = profile_dir / f"BR001_{EXPECTED_PROFILE_KIND}.csv.gz"
    pd.DataFrame(
        {
            "Metadata_Batch": [
                EXPECTED_BATCH,
                EXPECTED_BATCH,
                EXPECTED_BATCH,
                EXPECTED_BATCH,
                EXPECTED_BATCH,
                EXPECTED_BATCH,
            ],
            "Metadata_Plate": ["BR001", "BR001", "BR002", "BR002", "BR003", "BR003"],
            "Metadata_Well": ["A01", "A02", "A01", "A02", "B01", "B02"],
            "Metadata_broad_sample": ["BRD-A", "BRD-A", "BRD-A", "BRD-B", "BRD-B", "BRD-B"],
            "Metadata_pert_iname": [
                "compound-a",
                "compound-a",
                "compound-a",
                "compound-b",
                "compound-b",
                "compound-b",
            ],
            "Metadata_pert_type": ["trt_cp"] * 6,
            "Cells_AreaShape_Area": [1.0, 0.95, 0.9, 0.05, 0.0, 0.1],
            "Cytoplasm_Texture_InfoMeas": [0.0, 0.05, 0.1, 0.9, 1.0, 0.95],
            "Nuclei_Intensity_MeanIntensity": [0.9, 0.85, 0.8, 0.2, 0.1, 0.15],
        }
    ).to_csv(profile_path, index=False)
    return profile_path


def run_phase2_jump_smoke(
    out_dir: Path | str = Path("outputs/phase2_jump_smoke"),
) -> dict[str, Any]:
    """Run audit, index, and diagnostics on synthetic JUMP pilot data."""

    out_dir = Path(out_dir)
    synthetic_root = out_dir / "synthetic_data" / "jump_pilot"
    index_dir = out_dir / "jump_pilot_index"
    diagnostics_dir = out_dir / "jump_pilot_diagnostics"
    out_dir.mkdir(parents=True, exist_ok=True)

    profile_path = write_synthetic_jump_pilot(synthetic_root)

    audit = audit_jump_pilot(synthetic_root)
    audit_path = out_dir / "jump_pilot_inventory.json"
    audit_path.write_text(json.dumps(audit, indent=2) + "\n")

    index_metadata = build_jump_profile_index(synthetic_root, out_dir=index_dir)
    index_metadata_path = index_dir / "index_metadata.json"

    per_query, diagnostics_summary, diagnostics_metadata = run_jump_profile_diagnostics(
        synthetic_root,
        top_k=[1, 2],
        seed=7,
    )
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    per_query_path = diagnostics_dir / "profile_neighbor_diagnostics.csv"
    diagnostics_summary_path = diagnostics_dir / "profile_neighbor_diagnostics_summary.csv"
    diagnostics_json_path = diagnostics_dir / "profile_neighbor_diagnostics_summary.json"
    per_query.to_csv(per_query_path, index=False)
    diagnostics_summary.to_csv(diagnostics_summary_path, index=False)
    diagnostics_json_path.write_text(
        json.dumps(
            {
                "metadata": diagnostics_metadata,
                "summary": diagnostics_summary.to_dict(orient="records"),
            },
            indent=2,
        )
        + "\n"
    )
    report_path = make_phase2_jump_report(
        inventory=audit,
        index_metadata=index_metadata,
        diagnostics_summary=diagnostics_summary,
        diagnostics_metadata=diagnostics_metadata,
        out_path=out_dir / "phase2_jump_report.md",
    )

    diagnostic_metrics = _summary_metrics(diagnostics_summary)
    summary = {
        "audit_completed": True,
        "synthetic_data_root": str(synthetic_root),
        "synthetic_profile_path": str(profile_path),
        "audit_path": str(audit_path),
        "index_metadata_path": str(index_metadata_path),
        "diagnostics_output_path": str(diagnostics_summary_path),
        "diagnostics_json_path": str(diagnostics_json_path),
        "report_path": str(report_path),
        "number_of_rows_indexed": index_metadata["number_of_rows"],
        "number_of_numeric_feature_columns": index_metadata[
            "number_of_numeric_feature_columns"
        ],
        "diagnostics": diagnostic_metrics,
        "local_only_note": (
            "Synthetic smoke outputs are local-only artifacts and should not be committed."
        ),
    }
    (out_dir / "smoke_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def _summary_metrics(summary: pd.DataFrame) -> dict[str, float]:
    if summary.empty:
        return {}
    metrics = summary.set_index("metric")["value"].to_dict()
    wanted = [
        "same_batch_at_1",
        "same_plate_at_1",
        "same_well_at_1",
        "same_perturbation_treatment_at_1",
        "random_same_perturbation_treatment_at_1",
        "shuffled_same_perturbation_treatment_at_1",
    ]
    return {metric: float(metrics[metric]) for metric in wanted if metric in metrics}


def print_summary(summary: dict[str, Any]) -> None:
    print("Phase 2 JUMP smoke workflow complete")
    print(f"Audit completed: {summary['audit_completed']}")
    print(f"Index metadata path: {summary['index_metadata_path']}")
    print(f"Diagnostics output path: {summary['diagnostics_output_path']}")
    print(f"Report path: {summary['report_path']}")
    print(f"Rows indexed: {summary['number_of_rows_indexed']}")
    print(f"Numeric feature columns: {summary['number_of_numeric_feature_columns']}")
    if summary["diagnostics"]:
        print("Diagnostics:")
        for metric, value in summary["diagnostics"].items():
            print(f"  {metric}: {value:.4f}")
    print(summary["local_only_note"])


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("outputs/phase2_jump_smoke"),
        help="Local output directory for synthetic smoke data and generated artifacts.",
    )
    args = parser.parse_args()

    summary = run_phase2_jump_smoke(args.out)
    print_summary(summary)


if __name__ == "__main__":
    main()
