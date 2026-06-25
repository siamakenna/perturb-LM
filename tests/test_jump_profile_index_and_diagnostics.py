from __future__ import annotations

from pathlib import Path

import pandas as pd

from perturb_lm.data.jump import build_jump_profile_index, run_jump_profile_diagnostics
from perturb_lm.retrieval.index import load_index_matrix


def write_tiny_jump_profile(data_root: Path) -> Path:
    profile_dir = data_root / "profiles" / "2020_11_04_CPJUMP1" / "BR001"
    profile_dir.mkdir(parents=True)
    profile_path = profile_dir / "BR001_normalized_feature_select_negcon_batch.tsv.gz"
    pd.DataFrame(
        {
            "Metadata_Batch": [
                "2020_11_04_CPJUMP1",
                "2020_11_04_CPJUMP1",
                "2020_11_04_CPJUMP1",
                "2020_11_04_CPJUMP1",
                "2020_11_04_CPJUMP1",
            ],
            "Metadata_Plate": ["BR001", "BR001", "BR002", "BR003", "BR003"],
            "Metadata_Well": ["A01", "A02", "A01", "B01", "B02"],
            "Metadata_broad_sample": ["BRD-A", "BRD-A", "BRD-A", "BRD-B", "BRD-B"],
            "Metadata_pert_iname": [
                "compound-a",
                "compound-a",
                "compound-a",
                "compound-b",
                "compound-b",
            ],
            "Cells_AreaShape_Area": [1.0, 0.95, 0.9, 0.0, 0.05],
            "Nuclei_Texture_Info": [0.0, 0.05, 0.1, 1.0, 0.95],
            "Metadata_numeric_should_not_be_feature": [1, 2, 3, 4, 5],
        }
    ).to_csv(profile_path, sep="\t", index=False)
    return profile_path


def test_build_jump_profile_index_writes_metadata_and_reuses_index_artifacts(tmp_path) -> None:
    data_root = tmp_path / "jump_pilot"
    profile_path = write_tiny_jump_profile(data_root)
    out_dir = tmp_path / "jump_pilot_index"

    metadata = build_jump_profile_index(data_root, out_dir=out_dir)
    embeddings, id_mapping, saved_metadata = load_index_matrix(out_dir)

    assert metadata["dataset"] == "jump_pilot"
    assert metadata["input_profile_file_path"] == str(profile_path)
    assert metadata["number_of_rows"] == 5
    assert metadata["number_of_numeric_feature_columns"] == 2
    assert metadata["number_of_metadata_columns"] == 6
    assert metadata["detected_batch_column"] == "Metadata_Batch"
    assert metadata["detected_plate_column"] == "Metadata_Plate"
    assert metadata["detected_well_column"] == "Metadata_Well"
    assert metadata["detected_perturbation_treatment_columns"] == [
        "Metadata_broad_sample",
        "Metadata_pert_iname",
    ]
    assert metadata["index_type"] == "sklearn-nearest-neighbors"
    assert metadata["distance_metric"] == "cosine"
    assert "Metadata_numeric_should_not_be_feature" not in metadata[
        "detected_numeric_feature_columns"
    ]
    assert embeddings.shape == (5, 2)
    assert list(id_mapping.columns) == ["profile_id", "row_index"]
    assert (out_dir / "profile_metadata.csv").exists()
    assert saved_metadata["index_type"] == "sklearn-nearest-neighbors"


def test_run_jump_profile_diagnostics_reports_controls(tmp_path) -> None:
    data_root = tmp_path / "jump_pilot"
    write_tiny_jump_profile(data_root)

    per_query, summary, metadata = run_jump_profile_diagnostics(
        data_root,
        top_k=[1, 2],
        seed=13,
    )
    metrics = summary.set_index("metric")["value"]

    assert metadata["diagnostic_columns"] == [
        {"diagnostic": "batch", "column": "Metadata_Batch"},
        {"diagnostic": "plate", "column": "Metadata_Plate"},
        {"diagnostic": "well", "column": "Metadata_Well"},
        {"diagnostic": "perturbation_treatment", "column": "Metadata_broad_sample"},
    ]
    assert metrics["same_perturbation_treatment_at_1"] == 1.0
    assert 0.0 < metrics["random_same_perturbation_treatment_at_1"] < 1.0
    assert "shuffled_same_perturbation_treatment_at_1" in set(summary["metric"])
    assert set(per_query["diagnostic"]) == {
        "batch",
        "plate",
        "well",
        "perturbation_treatment",
    }
