import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from perturb_lm.modeling.phase3c import (
    LinearSyntheticTextEncoder,
    build_identifier_stripped_query_table,
    consensus_profiles,
    filter_phase3c_labeled_profiles,
    make_phase3c_split,
    make_synthetic_phase3c_profiles,
    run_phase3c_alignment,
    run_synthetic_phase3c_alignment_smoke,
    validate_identifier_stripped_text,
    validate_phase3c_qc_population,
    write_phase3c_public_safe_summary,
)
from perturb_lm.modeling.preprocessing import MorphologyPreprocessor
from scripts.run_phase3c_alignment import _build_run_manifest_payload


def test_identifier_stripped_query_policy_rejects_target_sequences():
    profiles, _ = make_synthetic_phase3c_profiles(seed=0, n_treatments=4)
    queries = build_identifier_stripped_query_table(profiles)
    assert "forbidden-sequence" not in " ".join(queries["query_text"].astype(str))
    assert not any(
        treatment in query_text
        for treatment in profiles["treatment"].astype(str).unique()
        for query_text in queries["query_text"].astype(str)
    )
    bad = queries.copy()
    bad.loc[0, "query_text"] = str(profiles.loc[0, "Metadata_target_sequence"])
    with pytest.raises(ValueError, match="prohibited"):
        validate_identifier_stripped_text(bad, profiles)


def test_gene_aware_m0_allows_gene_and_rejects_direct_identifiers():
    profiles = pd.DataFrame(
        {
            "profile_id": ["profile-a", "profile-b"],
            "treatment": ["treatment-a", "treatment-b"],
            "Metadata_gene": ["GENE_SENTINEL_A", "GENE_SENTINEL_B"],
            "Metadata_pert_type": ["crispr", "crispr"],
            "Metadata_control_type": ["", ""],
            "Metadata_negcon_control_type": ["", ""],
            "Metadata_broad_sample": [
                "BROAD_SAMPLE_SENTINEL_A",
                "BROAD_SAMPLE_SENTINEL_B",
            ],
        }
    )

    queries = build_identifier_stripped_query_table(profiles)
    query_text = " ".join(queries["query_text"].astype(str))

    assert "GENE_SENTINEL_A" in query_text
    assert "GENE_SENTINEL_B" in query_text
    assert "BROAD_SAMPLE_SENTINEL_A" not in query_text
    assert "BROAD_SAMPLE_SENTINEL_B" not in query_text

    bad = queries.copy()
    bad.loc[0, "query_text"] = "BROAD_SAMPLE_SENTINEL_A"

    with pytest.raises(ValueError, match="prohibited"):
        validate_identifier_stripped_text(bad, profiles)


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("Metadata_target_sequence", "SEQUENCE_SENTINEL"),
        ("Metadata_broad_sample", "BROAD_SAMPLE_SENTINEL"),
        ("Metadata_pert_iname", "PERT_INAME_SENTINEL"),
        ("Metadata_pert_id", "PERT_ID_SENTINEL"),
        ("Metadata_smiles", "SMILES_SENTINEL"),
        ("Metadata_InChIKey", "INCHIKEY_SENTINEL"),
        ("Metadata_Plate", "PLATE_SENTINEL"),
        ("Metadata_Well", "WELL_SENTINEL"),
        ("Metadata_Batch", "BATCH_SENTINEL"),
        ("Metadata_Inferred_Batch", "INFERRED_BATCH_SENTINEL"),
        ("profile_id", "PROFILE_SENTINEL"),
        ("source_profile_file", "SOURCE_FILE_SENTINEL"),
        ("source_profile_row", "SOURCE_ROW_SENTINEL"),
    ],
)
def test_gene_aware_m0_rejects_each_prohibited_field(column, value):
    profiles = pd.DataFrame(
        {
            "profile_id": ["profile-a", "profile-b"],
            "treatment": ["treatment-a", "treatment-b"],
            "Metadata_gene": ["GENE_SENTINEL_A", "GENE_SENTINEL_B"],
            "Metadata_pert_type": ["crispr", "crispr"],
            "Metadata_control_type": ["", ""],
            "Metadata_negcon_control_type": ["", ""],
        }
    )
    profiles[column] = [value, f"{value}_OTHER"]

    queries = build_identifier_stripped_query_table(profiles)
    query_text = " ".join(queries["query_text"].astype(str))

    assert value not in query_text

    bad = queries.copy()
    bad.loc[0, "query_text"] = value

    with pytest.raises(ValueError, match="prohibited"):
        validate_identifier_stripped_text(bad, profiles)


def test_phase3c_population_filter_reports_4524_to_4190():
    profiles = pd.DataFrame(
        {
            "profile_id": [f"profile-{index}" for index in range(4524)],
            "treatment": [
                *[f"treatment-{index % 641}" for index in range(4190)],
                *([np.nan] * 330),
                "",
                "nan",
                "none",
                "<NA>",
            ],
        }
    )

    filtered, population = filter_phase3c_labeled_profiles(profiles)

    assert len(filtered) == 4190
    assert population == {
        "population_inclusion_rule": "profiles with non-missing treatment labels",
        "qc_profile_count": 4524,
        "labeled_profile_count": 4190,
        "excluded_unlabeled_profile_count": 334,
        "warnings": ["Excluded 334 of 4524 QC profiles because treatment labels were missing."],
    }
    assert filtered["treatment"].map(lambda value: str(value).strip()).ne("").all()


def test_phase3c_qc_population_requires_expected_files_and_rows():
    profile_paths = [
        Path("data/raw/jump_pilot/profiles/2020_11_04_CPJUMP1")
        / plate
        / f"{plate}_normalized_feature_select_negcon_batch.csv.gz"
        for plate in [f"BR{value:08d}" for value in range(116991, 117003)]
    ]
    profiles = pd.DataFrame(index=range(4524))

    assert validate_phase3c_qc_population(profiles, profile_paths) == {
        "input_profile_file_count": 12,
        "qc_profile_count": 4524,
    }
    with pytest.raises(ValueError, match="expected 4524 QC profiles"):
        validate_phase3c_qc_population(profiles.iloc[:-1], profile_paths)
    with pytest.raises(ValueError, match="expected 12 profile files"):
        validate_phase3c_qc_population(profiles, profile_paths[:-1])
    wrong_batch_paths = [
        Path("data/raw/jump_pilot/profiles/wrong_batch") / path.parent.name / path.name
        for path in profile_paths
    ]
    with pytest.raises(ValueError, match="must come from batch"):
        validate_phase3c_qc_population(profiles, wrong_batch_paths)


def test_phase3c_cli_run_manifest_includes_query_contract_metadata():
    result = {
        "split": "held_out_plate",
        "retrieval_filter": "exclude_same_plate_and_well",
        "status": "completed",
        "seed": 0,
        "git_commit": "abc123",
        "git_branch": "test-branch",
        "git_dirty": False,
        "query_condition_version": "M0_GENE_AWARE_V1",
        "query_model_visible_fields": [
            "Metadata_gene",
            "Metadata_pert_type",
            "Metadata_control_type",
            "Metadata_negcon_control_type",
        ],
        "query_inventory_sha256": "a" * 64,
        "query_count": 1079,
        "evaluable_query_count": 180,
        "nonevaluable_query_count": 899,
        "query_coverage": 180 / 1079,
        "positive_count_histogram": {"0": 899, "1": 180},
        "max_positive_count": 1,
        "population_inclusion_rule": "non-missing treatment label",
        "labeled_profile_count": 4190,
        "excluded_unlabeled_profile_count": 334,
    }
    input_population = {
        "input_profile_file_count": 12,
        "qc_profile_count": 4524,
    }
    encoder_payload = {"model_name": "deterministic_fake_text_encoder"}

    payload = _build_run_manifest_payload(
        result,
        encoder_payload,
        input_population,
    )

    assert payload["query_condition_version"] == "M0_GENE_AWARE_V1"
    assert payload["query_model_visible_fields"] == result[
        "query_model_visible_fields"
    ]
    assert payload["query_inventory_sha256"] == "a" * 64
    assert payload["query_count"] == 1079
    assert payload["evaluable_query_count"] == 180
    assert payload["nonevaluable_query_count"] == 899
    assert payload["query_coverage"] == pytest.approx(180 / 1079)
    assert payload["positive_count_histogram"] == {"0": 899, "1": 180}
    assert payload["max_positive_count"] == 1
    assert payload["qc_profile_count"] == 4524
    assert payload["input_profile_file_count"] == 12


def test_phase3c_runner_filters_unlabeled_profiles_before_split_and_reports_manifest(tmp_path):
    profiles, features = make_synthetic_phase3c_profiles(seed=5, n_treatments=8)
    unlabeled = profiles.iloc[:3].copy()
    unlabeled["profile_id"] = ["unlabeled-0", "unlabeled-1", "unlabeled-2"]
    unlabeled["treatment"] = [np.nan, "", "null"]
    qc_profiles = pd.concat([profiles, unlabeled], ignore_index=True)

    result = run_phase3c_alignment(
        qc_profiles,
        encoder=LinearSyntheticTextEncoder(seed=5),
        split_type="held_out_treatment",
        seed=5,
        feature_columns=features,
        bootstrap_samples=5,
    )

    assert result["qc_profile_count"] == len(qc_profiles)
    assert result["labeled_profile_count"] == len(profiles)
    assert result["excluded_unlabeled_profile_count"] == 3
    assert result["train_profiles"] + result["test_profiles"] == len(profiles)
    assert "Excluded 3" in result["warnings"][0]

    out = tmp_path / "outputs" / "phase3c_population"
    write_phase3c_public_safe_summary(result, out)
    manifest = json.loads((out / "phase3c_public_safe_manifest.json").read_text())
    assert manifest["qc_profile_count"] == len(qc_profiles)
    assert manifest["labeled_profile_count"] == len(profiles)
    assert manifest["excluded_unlabeled_profile_count"] == 3
    assert "git_commit" in manifest
    assert "git_branch" in manifest
    assert "git_dirty" in manifest
    assert manifest["query_condition_version"] == "M0_GENE_AWARE_V1"
    assert manifest["query_model_visible_fields"] == [
        "Metadata_gene",
        "Metadata_pert_type",
        "Metadata_control_type",
        "Metadata_negcon_control_type",
    ]

    query_inventory_sha256 = manifest["query_inventory_sha256"]
    assert len(query_inventory_sha256) == 64
    assert all(character in "0123456789abcdef" for character in query_inventory_sha256)
    assert manifest["query_count"] > 0
    assert (
        manifest["evaluable_query_count"] + manifest["nonevaluable_query_count"]
        == manifest["query_count"]
    )
    assert manifest["query_coverage"] == pytest.approx(
        manifest["evaluable_query_count"] / manifest["query_count"]
    )
    assert isinstance(manifest["positive_count_histogram"], dict)
    assert sum(manifest["positive_count_histogram"].values()) == manifest["query_count"]
    assert manifest["max_positive_count"] >= 0


def test_held_out_treatment_split_has_no_overlap_and_batch_can_be_unavailable():
    profiles, _ = make_synthetic_phase3c_profiles(seed=1, n_treatments=8)
    split = make_phase3c_split(profiles, split_type="held_out_treatment", seed=1)
    train = set(split.frame.loc[split.frame["split"] == "train", "treatment"])
    test = set(split.frame.loc[split.frame["split"] == "test", "treatment"])
    assert train.isdisjoint(test)
    batch = make_phase3c_split(profiles, split_type="held_out_batch", seed=1)
    assert batch.frame["split"].eq("unavailable").all()
    assert "unavailable" in batch.warnings[0]


def test_train_only_preprocessing_and_consensus_construction():
    profiles, features = make_synthetic_phase3c_profiles(seed=2, n_treatments=6)
    split = make_phase3c_split(profiles, split_type="held_out_plate", seed=2)
    train = split.frame[split.frame["split"] == "train"]
    preprocessor = MorphologyPreprocessor().fit(train, feature_columns=features, fit_split="train")
    assert preprocessor.fit_metadata_["fit_split"] == "train"
    consensus = consensus_profiles(
        split.frame,
        feature_columns=features,
        method="median",
        split_column="split",
        allowed_split="train",
    )
    assert set(consensus["split"]) == {"train"}
    assert "replicate_count" in consensus.columns


def test_phase3c_synthetic_smoke_succeeds_without_real_model(tmp_path):
    out = tmp_path / "outputs" / "phase3c_alignment_smoke"
    result = run_synthetic_phase3c_alignment_smoke(out_dir=out, seed=0)
    summary = result["summary"]
    assert result["status"] == "completed"
    assert (out / "phase3c_alignment_summary.csv").exists()
    assert (out / "phase3c_public_safe_manifest.json").exists()
    counts = summary[
        (summary["comparison"] == "point_estimate") & (summary["metric"] == "average_precision")
    ][["mode", "n_total_queries", "n_evaluable_queries"]]
    assert counts["n_total_queries"].nunique() == 1
    assert counts["n_evaluable_queries"].min() > 0
    projection_map = summary[
        (summary["mode"] == "frozen_text_embeddings_linear_projection")
        & (summary["comparison"] == "point_estimate")
        & (summary["metric"] == "average_precision")
    ]["estimate"].iloc[0]
    random_map = summary[
        (summary["mode"] == "random")
        & (summary["comparison"] == "point_estimate")
        & (summary["metric"] == "average_precision")
    ]["estimate"].iloc[0]
    assert projection_map > random_map


def test_projection_fit_uses_train_rows_only():
    profiles, features = make_synthetic_phase3c_profiles(seed=3, n_treatments=10)
    split = make_phase3c_split(profiles, split_type="held_out_plate", seed=3)
    train = split.frame[split.frame["split"] == "train"]
    test = split.frame[split.frame["split"] == "test"]
    encoder = LinearSyntheticTextEncoder(seed=3)
    train_embeddings = encoder.encode(train["Metadata_gene"].astype(str).tolist())
    test_embeddings = encoder.encode(test["Metadata_gene"].astype(str).tolist())
    assert train_embeddings.shape[0] == len(train)
    assert test_embeddings.shape[0] == len(test)
    assert set(train["profile_id"]).isdisjoint(set(test["profile_id"]))
    assert features
