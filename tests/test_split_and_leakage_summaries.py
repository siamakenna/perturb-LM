from __future__ import annotations

import json

import pandas as pd

from perturb_lm.data.jump import run_jump_profile_diagnostics
from perturb_lm.engineering.summaries import (
    build_neighbor_leakage_summary,
    build_split_summary,
    write_leakage_summary,
    write_split_summary,
)


def _split_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "dataset": ["rxrx1"] * 6,
            "site_id": [f"s{i}" for i in range(6)],
            "experiment": ["batch1", "batch1", "batch2", "batch2", "batch3", "batch3"],
            "plate": ["p1", "p1", "p2", "p2", "p3", "p3"],
            "well": ["A01", "A02", "A01", "A02", "B01", "B02"],
            "perturbation_id": ["a", "b", "a", "c", "d", "d"],
            "perturbation_name": ["A", "B", "A", "C", "D", "D"],
            "cell_type": ["cell"] * 6,
            "condition_label": ["control"] * 6,
            "concentration": ["1"] * 6,
        }
    )


def _jump_profile(data_root) -> None:
    profile_dir = data_root / "profiles" / "2020_11_04_CPJUMP1" / "BR001"
    profile_dir.mkdir(parents=True)
    pd.DataFrame(
        {
            "Metadata_Batch": ["batch1", "batch1", "batch2", "batch2"],
            "Metadata_Plate": ["plate1", "plate1", "plate2", "plate2"],
            "Metadata_Well": ["A01", "A02", "A01", "A02"],
            "Metadata_broad_sample": ["BRD-A", "BRD-A", "BRD-B", "BRD-B"],
            "Cells_AreaShape_Area": [1.0, 0.9, 0.0, 0.1],
            "Nuclei_Texture_Info": [0.0, 0.1, 1.0, 0.9],
        }
    ).to_csv(profile_dir / "BR001_normalized_feature_select_negcon_batch.csv", index=False)


def test_split_summary_reports_held_out_plate_counts(tmp_path) -> None:
    frame = _split_frame()
    frame["split"] = ["train", "train", "test", "test", "train", "train"]

    summary = build_split_summary(
        frame,
        split_name="held_out_plate",
        split_type="held_out_plate",
    )
    paths = write_split_summary(summary, tmp_path)
    csv_summary = pd.read_csv(paths["split_summary_csv"])

    assert summary["train_row_count"] == 4
    assert summary["test_row_count"] == 2
    assert summary["train_plate_count"] == 2
    assert summary["test_plate_count"] == 1
    assert summary["treatment_overlap_count"] == 1
    assert summary["n_evaluable_queries"] == 1
    assert csv_summary.loc[0, "split_name"] == "held_out_plate"
    assert (tmp_path / "split_summary.json").exists()


def test_split_summary_reports_held_out_well_counts() -> None:
    frame = _split_frame()
    frame["split"] = ["train", "test", "train", "test", "train", "test"]

    summary = build_split_summary(
        frame,
        split_name="held_out_well",
        split_type="held_out_well",
    )

    assert summary["train_well_count"] == 3
    assert summary["test_well_count"] == 3
    assert summary["train_perturbation_count"] == 2
    assert summary["test_perturbation_count"] == 3


def test_split_summary_reports_one_batch_warning_without_crashing() -> None:
    frame = _split_frame()
    frame["experiment"] = "batch1"
    frame["split"] = "train"

    summary = build_split_summary(
        frame,
        split_name="held_out_batch",
        split_type="held_out_batch",
    )

    assert summary["train_batch_count"] == 1
    assert summary["test_batch_count"] == 0
    assert summary["test_row_count"] == 0
    assert any("only 1 batch group" in warning for warning in summary["warnings"])
    assert any("No test rows" in warning for warning in summary["warnings"])


def test_split_summary_reports_held_out_perturbation_overlap() -> None:
    frame = _split_frame()
    frame["split"] = ["train", "train", "train", "test", "test", "test"]

    summary = build_split_summary(
        frame,
        split_name="held_out_perturbation",
        split_type="held_out_perturbation",
    )

    assert summary["train_perturbation_count"] == 2
    assert summary["test_perturbation_count"] == 2
    assert summary["treatment_overlap_count"] == 0
    assert summary["n_evaluable_queries"] == 0


def test_split_summary_missing_columns_warns_without_crashing() -> None:
    summary = build_split_summary(
        pd.DataFrame({"split": ["train", "test"]}),
        split_name="held_out_plate",
        split_type="held_out_plate",
    )

    assert summary["train_row_count"] == 1
    assert summary["test_row_count"] == 1
    assert summary["train_plate_count"] is None
    assert any("No plate column" in warning for warning in summary["warnings"])


def test_neighbor_leakage_summary_exports_evaluable_counts_and_safe_payload(tmp_path) -> None:
    data_root = tmp_path / "jump_pilot"
    _jump_profile(data_root)
    _, summary, metadata = run_jump_profile_diagnostics(data_root, top_k=[1], seed=3)

    payload = build_neighbor_leakage_summary(summary, metadata)
    paths = write_leakage_summary(payload, tmp_path)
    csv_summary = pd.read_csv(paths["leakage_summary_csv"])
    dashboard_text = paths["dashboard_leakage_summary_json"].read_text()
    dashboard = json.loads(dashboard_text)
    treatment = csv_summary[csv_summary["metric"] == "same_treatment_at_1"].iloc[0]

    assert treatment["n_queries"] == 4
    assert treatment["n_evaluable_queries"] == 4
    assert treatment["count"] == 4
    assert dashboard["report_type"] == "dashboard_leakage_summary"
    assert dashboard["n_evaluable_queries"] == 4
    assert "source_profile_file" not in dashboard_text
    assert str(tmp_path) not in dashboard_text
    assert "profile_id" not in dashboard_text
