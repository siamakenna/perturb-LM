from __future__ import annotations

import pytest

from perturb_lm.modeling.experiment_config import (
    load_phase3b_config,
    validate_phase3b_config,
)


def _valid_config() -> dict:
    return {
        "dataset_track": "jump_cpjump1_profiles",
        "profile_data_root": "data/raw/jump_pilot",
        "output_root": "outputs/phase3b",
        "primary_split": "held_out_treatment",
        "secondary_splits": [
            "held_out_plate",
            "exclude_same_plate",
            "exclude_same_well",
            "exclude_same_plate_and_well",
        ],
        "unavailable_splits": {
            "held_out_batch": {
                "available": False,
                "reason": "Only one inferred batch is available.",
            }
        },
        "seeds": [0, 1, 2],
        "top_k": [1, 5, 10],
        "preprocessing": {
            "feature_policy": "cell_painting_numeric_only",
            "imputation": "median",
            "scaling": "standard",
            "fit_scope": "train_only",
            "near_zero_variance_threshold": 1e-12,
            "harmonization_policy": "strict_intersection",
        },
        "evaluable_query_thresholds": {
            "held_out_treatment": 100,
            "held_out_plate": 500,
            "exclude_same_plate": 100,
            "exclude_same_well": 100,
            "exclude_same_plate_and_well": 100,
            "held_out_batch": {
                "available": False,
                "reason": "Only one inferred batch is available.",
            },
        },
        "aggregation": "perturbation_level",
        "query_text": {
            "allowed_fields": ["Metadata_gene", "Metadata_pert_type"],
            "prohibited_identifier_fields": ["Metadata_broad_sample", "Metadata_Plate"],
        },
        "metrics": [
            "mean_average_precision",
            "hit_at_1",
            "hit_at_5",
            "hit_at_10",
            "recall_at_1",
            "recall_at_5",
            "recall_at_10",
            "enrichment_over_random",
            "n_total_queries",
            "n_evaluable_queries",
        ],
        "controls": [
            "random",
            "shuffled_label",
            "metadata_tfidf",
            "identifier_stripped_tfidf",
            "frozen_text_embeddings",
            "linear_projection",
        ],
        "leakage_filters": ["exclude_same_plate"],
        "artifact_policy": {
            "commit_generated_outputs": False,
            "commit_embeddings": False,
            "commit_model_weights": False,
            "commit_indexes": False,
            "commit_row_level_data": False,
        },
    }


def test_phase3b_config_file_validates() -> None:
    config = load_phase3b_config("configs/phase3b_linear_projection_v1.yaml")

    assert config["primary_split"] == "held_out_plate"
    assert config["seeds"] == [0, 1, 2, 3, 4]
    assert "Metadata_target_sequence" not in config["query_text"]["allowed_fields"]
    assert "Metadata_target_sequence" in config["query_text"]["prohibited_identifier_fields"]
    assert config["evaluable_query_thresholds"]["held_out_plate"] == 500


def test_phase3b_config_rejects_missing_required_field() -> None:
    config = _valid_config()
    config.pop("controls")

    with pytest.raises(ValueError, match="missing required keys"):
        validate_phase3b_config(config)


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("seeds", [0, 0, 1], "seeds must be unique"),
        ("seeds", [0, 1], "at least three"),
        ("top_k", [5, 1], "sorted and unique"),
        ("top_k", [0, 5], "positive integers"),
        ("primary_split", "held_out_batch", "Unsupported primary split"),
        ("secondary_splits", ["made_up_split"], "Unsupported secondary split"),
        ("output_root", "public/results", "ignored local artifact directory"),
    ],
)
def test_phase3b_config_rejects_invalid_values(field: str, value: object, match: str) -> None:
    config = _valid_config()
    config[field] = value

    with pytest.raises(ValueError, match=match):
        validate_phase3b_config(config)


def test_phase3b_config_rejects_prohibited_text_fields() -> None:
    config = _valid_config()
    config["query_text"]["allowed_fields"].append("Metadata_broad_sample")

    with pytest.raises(ValueError, match="Prohibited identifier fields"):
        validate_phase3b_config(config)


def test_phase3b_config_rejects_one_query_scientific_threshold() -> None:
    config = _valid_config()
    config["evaluable_query_thresholds"]["held_out_treatment"] = 1

    with pytest.raises(ValueError, match="at least 2"):
        validate_phase3b_config(config)
