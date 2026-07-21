from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from perturb_lm.data.profile_qc import (
    dashboard_safe_profile_qc_summary,
    profile_qc_from_frames,
)


def test_profile_qc_reports_aggregate_feature_quality_without_identifiers() -> None:
    frame_a = pd.DataFrame(
        {
            "Metadata_Batch": ["batch-a", "batch-a", "batch-a"],
            "Metadata_Plate": ["plate-a", "plate-a", "plate-b"],
            "Metadata_Well": ["A01", "A01", "A02"],
            "Metadata_broad_sample": ["BRD-A", "BRD-A", "BRD-B"],
            "Cells_valid": [1.0, 2.0, 3.0],
            "Cells_missing": [np.nan, 1.0, 2.0],
            "Cells_infinite": [0.0, np.inf, 2.0],
            "Cells_all_missing": [np.nan, np.nan, np.nan],
            "Cells_zero": [4.0, 4.0, 4.0],
            "Cells_near_zero": [1.0, 1.0 + 1e-8, 1.0 + 2e-8],
            "Nuclei_duplicate_a": [5.0, 6.0, 7.0],
            "Nuclei_duplicate_b": [5.0, 6.0, 7.0],
            "Image_extreme": [0.0, 2e6, 3.0],
        }
    )
    frame_b = pd.DataFrame(
        {
            "Metadata_Batch": ["batch-a"],
            "Metadata_Plate": ["plate-c"],
            "Metadata_Well": ["A03"],
            "Metadata_broad_sample": ["BRD-C"],
            "Cells_valid": [4.0],
            "Cells_missing": [3.0],
            "Cells_extra_only_in_b": [1.0],
        }
    )

    report = profile_qc_from_frames([frame_a, frame_b])
    safe = dashboard_safe_profile_qc_summary(report)
    serialized = json.dumps(safe)

    assert safe["total_profile_rows"] == 4
    assert safe["missing_value_count"] >= 4
    assert safe["infinite_value_count"] == 1
    assert safe["all_missing_feature_count"] >= 1
    assert safe["zero_variance_feature_count"] >= 1
    assert safe["near_zero_variance_feature_count"] >= 1
    assert safe["duplicate_feature_value_count"] >= 1
    assert safe["extreme_value_count"] >= 1
    assert safe["schema_consistent_across_files"] is False
    assert safe["features_present_in_some_files_missing_from_others_count"] > 0
    assert "Metadata_" not in serialized
    assert "BRD-" not in serialized
    assert "plate-" not in serialized
    assert "Cells_" not in serialized
    assert "/" not in serialized


def test_profile_qc_counts_duplicate_column_names() -> None:
    frame = pd.DataFrame(
        np.array([[1.0, 1.0, 2.0], [2.0, 2.0, 3.0]]),
        columns=["Cells_dup", "Cells_dup", "Cells_unique"],
    )

    report = profile_qc_from_frames([frame])

    assert report["duplicate_feature_name_count"] == 1
    assert report["duplicate_feature_column_count"] >= 1


def test_run_jump_profile_qc_cli_writes_dashboard_safe_output(tmp_path: Path) -> None:
    data_root = tmp_path / "jump_pilot"
    profile_dir = data_root / "profiles" / "2020_11_04_CPJUMP1" / "BR001"
    profile_dir.mkdir(parents=True)
    profile_path = profile_dir / "BR001_normalized_feature_select_negcon_batch.csv.gz"
    pd.DataFrame(
        {
            "Metadata_Batch": ["batch-a", "batch-a"],
            "Metadata_Plate": ["plate-a", "plate-b"],
            "Metadata_Well": ["A01", "A02"],
            "Metadata_broad_sample": ["BRD-A", "BRD-A"],
            "Cells_valid": [1.0, 2.0],
            "Nuclei_valid": [3.0, 4.0],
        }
    ).to_csv(profile_path, index=False)
    out = tmp_path / "qc"

    subprocess.run(
        [
            sys.executable,
            "scripts/run_jump_profile_qc.py",
            "--data-root",
            str(data_root),
            "--out",
            str(out),
        ],
        check=True,
    )

    safe = json.loads((out / "jump_profile_qc_dashboard_safe.json").read_text())
    assert safe["profile_file_count"] == 1
    assert safe["total_profile_rows"] == 2
