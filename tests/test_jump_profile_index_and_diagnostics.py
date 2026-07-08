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


def write_single_plate_profile_without_batch(data_root: Path) -> Path:
    profile_dir = data_root / "profiles" / "2020_11_04_CPJUMP1" / "BR001"
    profile_dir.mkdir(parents=True)
    profile_path = profile_dir / "BR001_normalized_feature_select_negcon_batch.csv.gz"
    pd.DataFrame(
        {
            "Metadata_Plate": ["BR001", "BR001", "BR001", "BR001"],
            "Metadata_Well": ["A01", "A02", "A03", "A04"],
            "Metadata_broad_sample": ["BRD-A", "BRD-A", "BRD-B", "BRD-C"],
            "Metadata_pert_iname": ["compound-a", "compound-a", "compound-b", "compound-c"],
            "Cells_AreaShape_Area": [1.0, 0.95, 0.0, 0.2],
            "Nuclei_Texture_Info": [0.0, 0.05, 1.0, 0.8],
        }
    ).to_csv(profile_path, index=False)
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
    assert (out_dir / "artifact_manifest.json").exists()
    assert (out_dir / "runtime_log.json").exists()
    assert saved_metadata["index_type"] == "sklearn-nearest-neighbors"
    assert saved_metadata["artifact_manifest_path"] == str(out_dir / "artifact_manifest.json")
    assert saved_metadata["runtime_log_path"] == str(out_dir / "runtime_log.json")


def test_jump_profile_index_infers_batch_from_profile_path(tmp_path) -> None:
    data_root = tmp_path / "jump_pilot"
    write_single_plate_profile_without_batch(data_root)

    metadata = build_jump_profile_index(data_root, out_dir=tmp_path / "index")
    profile_metadata = pd.read_csv(tmp_path / "index" / "profile_metadata.csv")

    assert metadata["detected_batch_column"] == "Metadata_Inferred_Batch"
    assert set(profile_metadata["Metadata_Inferred_Batch"]) == {"2020_11_04_CPJUMP1"}


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
    assert set(summary["filter_name"]) == {"unfiltered"}
    assert set(per_query["diagnostic"]) == {
        "batch",
        "plate",
        "well",
        "perturbation_treatment",
    }


def test_jump_profile_diagnostics_explain_single_plate_and_evaluable_queries(tmp_path) -> None:
    data_root = tmp_path / "jump_pilot"
    write_single_plate_profile_without_batch(data_root)

    _, summary, metadata = run_jump_profile_diagnostics(data_root, top_k=[1], seed=0)
    by_metric = summary.set_index("metric")

    assert metadata["detected_batch_column"] == "Metadata_Inferred_Batch"
    assert any("one plate" in warning for warning in metadata["warnings"])
    plate_row = by_metric.loc["same_plate_at_1"]
    assert "not informative" in plate_row["warning"]
    treatment_row = by_metric.loc["same_perturbation_treatment_at_1"]
    assert treatment_row["label_column"] == "Metadata_broad_sample"
    assert treatment_row["n_queries"] == 4
    assert treatment_row["n_evaluable_queries"] == 2
    assert treatment_row["n_positive_matches"] == 2
    assert treatment_row["value_all_queries"] < treatment_row["value_evaluable_queries"]
    assert "Only 2 of 4 queries are evaluable" in treatment_row["warning"]


def test_jump_profile_filtered_diagnostics_report_filter_labels_and_counts(tmp_path) -> None:
    data_root = tmp_path / "jump_pilot"
    write_tiny_jump_profile(data_root)

    _, summary, metadata = run_jump_profile_diagnostics(
        data_root,
        top_k=[1],
        filtered_presets=True,
        seed=2,
    )
    treatment = summary[
        (summary["diagnostic"] == "perturbation_treatment")
        & (summary["metric"] == "same_perturbation_treatment_at_1")
    ]
    by_filter = treatment.set_index("filter_name")

    assert {
        "unfiltered",
        "exclude_same_plate",
        "exclude_same_well",
        "exclude_same_plate_and_well",
    }.issubset(set(treatment["filter_name"]))
    assert by_filter.loc["exclude_same_plate", "excluded_label_columns"] == "Metadata_Plate"
    assert by_filter.loc["exclude_same_well", "excluded_label_columns"] == "Metadata_Well"
    assert (
        by_filter.loc["exclude_same_plate_and_well", "excluded_label_columns"]
        == "Metadata_Plate|Metadata_Well"
    )
    assert (
        by_filter.loc["exclude_same_plate", "n_candidates_after_filter_min"]
        < by_filter.loc["unfiltered", "n_candidates_after_filter_min"]
    )
    assert (
        by_filter.loc["exclude_same_well", "n_candidates_after_filter_min"]
        < by_filter.loc["unfiltered", "n_candidates_after_filter_min"]
    )
    assert metadata["filters"][0]["filter_name"] == "unfiltered"


def test_jump_profile_filtered_diagnostics_warn_when_no_candidates_remain(tmp_path) -> None:
    data_root = tmp_path / "jump_pilot"
    write_single_plate_profile_without_batch(data_root)

    _, summary, _ = run_jump_profile_diagnostics(
        data_root,
        top_k=[1],
        exclude_same_plate=True,
        seed=0,
    )
    treatment = summary[
        (summary["diagnostic"] == "perturbation_treatment")
        & (summary["metric"] == "same_perturbation_treatment_at_1")
        & (summary["filter_name"] == "exclude_same_plate")
    ].iloc[0]

    assert treatment["n_queries_with_candidates"] == 0
    assert treatment["n_candidates_after_filter_max"] == 0
    assert "No queries have candidate neighbors after filter exclude_same_plate" in treatment[
        "warning"
    ]
