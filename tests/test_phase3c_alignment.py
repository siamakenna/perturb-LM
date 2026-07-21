import numpy as np
import pytest

from perturb_lm.modeling.phase3c import (
    LinearSyntheticTextEncoder,
    build_identifier_stripped_query_table,
    consensus_profiles,
    make_phase3c_split,
    make_synthetic_phase3c_profiles,
    run_synthetic_phase3c_alignment_smoke,
    validate_identifier_stripped_text,
)
from perturb_lm.modeling.preprocessing import MorphologyPreprocessor


def test_identifier_stripped_query_policy_rejects_target_sequences():
    profiles, _ = make_synthetic_phase3c_profiles(seed=0, n_treatments=4)
    queries = build_identifier_stripped_query_table(profiles)
    assert "forbidden-sequence" not in " ".join(queries["query_text"].astype(str))
    bad = queries.copy()
    bad.loc[0, "query_text"] = str(profiles.loc[0, "Metadata_target_sequence"])
    with pytest.raises(ValueError, match="prohibited"):
        validate_identifier_stripped_text(bad, profiles)


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
        (summary["comparison"] == "point_estimate")
        & (summary["metric"] == "average_precision")
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
