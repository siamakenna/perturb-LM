from __future__ import annotations

import pandas as pd

from perturb_lm.data.jump import EXPECTED_METADATA_FILES, audit_jump_pilot
from scripts.audit_jump_pilot import format_audit_summary, truncate_inventory_for_print


def test_audit_jump_pilot_reports_expected_files_and_profile_columns(tmp_path) -> None:
    data_root = tmp_path / "jump_pilot"
    metadata_dir = data_root / "metadata"
    profile_dir = data_root / "profiles" / "2020_11_04_CPJUMP1" / "BR001"
    metadata_dir.mkdir(parents=True)
    profile_dir.mkdir(parents=True)

    for name in EXPECTED_METADATA_FILES:
        (metadata_dir / name).write_text("Metadata_Source\tvalue\nJUMP\t1\n")

    profile_path = profile_dir / "BR001_normalized_feature_select_negcon_batch.csv.gz"
    pd.DataFrame(
        {
            "Metadata_Batch": ["2020_11_04_CPJUMP1", "2020_11_04_CPJUMP1"],
            "Metadata_Plate": ["BR001", "BR001"],
            "Metadata_Well": ["A01", "A02"],
            "Metadata_broad_sample": ["BRD-A", "BRD-B"],
            "Metadata_pert_iname": ["compound-a", "compound-b"],
            "Cells_AreaShape_Area": [1.0, 2.0],
            "Nuclei_Texture_Info": [0.5, 0.7],
        }
    ).to_csv(profile_path, index=False)

    inventory = audit_jump_pilot(data_root)
    profile_summary = next(
        summary for summary in inventory["readable_files"] if summary["kind"] == "profile"
    )

    assert inventory["dataset"] == "jump_pilot"
    assert inventory["expected_batch"] == "2020_11_04_CPJUMP1"
    assert inventory["expected_profile_kind"] == "normalized_feature_select_negcon_batch"
    assert len(inventory["metadata_files_found"]) == len(EXPECTED_METADATA_FILES)
    assert inventory["missing_expected_files"] == []
    assert inventory["profile_files_found"][0]["relative_path"].endswith(profile_path.name)
    assert profile_summary["row_count"] == 2
    assert profile_summary["column_count"] == 7
    assert "Metadata_broad_sample" in inventory["detected_metadata_columns"]
    assert "Cells_AreaShape_Area" in inventory["detected_numeric_feature_columns"]
    assert inventory["likely_batch_column"] == "Metadata_Batch"
    assert inventory["likely_plate_column"] == "Metadata_Plate"
    assert inventory["likely_well_column"] == "Metadata_Well"
    assert inventory["likely_perturbation_treatment_columns"] == [
        "Metadata_broad_sample",
        "Metadata_pert_iname",
    ]
    assert inventory["warnings"] == []
    assert "should not be committed" in inventory["local_only_note"]


def test_audit_jump_pilot_warns_when_local_data_is_missing(tmp_path) -> None:
    data_root = tmp_path / "missing_jump_pilot"

    inventory = audit_jump_pilot(data_root)

    assert inventory["metadata_files_found"] == []
    assert inventory["profile_files_found"] == []
    assert sorted(inventory["missing_expected_files"]) == sorted(EXPECTED_METADATA_FILES)
    assert any("Local data root does not exist" in warning for warning in inventory["warnings"])
    assert any("No JUMP pilot profile files" in warning for warning in inventory["warnings"])


def test_audit_summary_output_can_limit_column_preview(tmp_path) -> None:
    data_root = tmp_path / "jump_pilot"
    profile_dir = data_root / "profiles" / "2020_11_04_CPJUMP1" / "BR001"
    profile_dir.mkdir(parents=True)
    profile_path = profile_dir / "BR001_normalized_feature_select_negcon_batch.csv"
    frame = pd.DataFrame(
        {
            "Metadata_Plate": ["BR001"],
            "Metadata_Well": ["A01"],
            "Metadata_broad_sample": ["BRD-A"],
            **{f"Cells_Feature_{index}": [float(index)] for index in range(5)},
        }
    )
    frame.to_csv(profile_path, index=False)

    inventory = audit_jump_pilot(data_root)
    summary = format_audit_summary(inventory, max_columns=2)
    truncated = truncate_inventory_for_print(inventory, max_columns=2)

    assert "JUMP pilot audit summary" in summary
    assert "... (3 more)" in summary
    assert len(truncated["detected_numeric_feature_columns"]) == 3
    assert truncated["detected_numeric_feature_columns"][-1] == "... (3 more)"
