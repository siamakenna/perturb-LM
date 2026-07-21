"""Validation for Phase 3B executable experiment configs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SUPPORTED_SPLITS = {
    "held_out_plate",
    "held_out_treatment",
    "exclude_same_plate",
    "exclude_same_well",
    "exclude_same_plate_and_well",
}
SUPPORTED_UNAVAILABLE_SPLITS = {"held_out_batch"}
SUPPORTED_CONTROLS = {
    "random",
    "shuffled_label",
    "metadata_tfidf",
    "identifier_stripped_tfidf",
    "frozen_text_embeddings",
    "linear_projection",
}
REQUIRED_METRICS = {
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
}
IGNORED_OUTPUT_ROOTS = {"outputs", "results", "models"}
REQUIRED_CONFIG_KEYS = {
    "dataset_track",
    "profile_data_root",
    "output_root",
    "primary_split",
    "secondary_splits",
    "seeds",
    "top_k",
    "preprocessing",
    "minimum_evaluable_queries",
    "aggregation",
    "query_text",
    "metrics",
    "controls",
    "leakage_filters",
    "artifact_policy",
}


def load_phase3b_config(path: Path | str) -> dict[str, Any]:
    """Load a Phase 3B config from YAML or JSON-compatible YAML."""

    text = Path(path).read_text()
    try:
        import yaml  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        payload = json.loads(text)
    else:
        payload = yaml.safe_load(text)
    if not isinstance(payload, dict):
        raise ValueError("Phase 3B config must load to a mapping.")
    return validate_phase3b_config(payload)


def validate_phase3b_config(config: dict[str, Any]) -> dict[str, Any]:
    """Validate the Phase 3B linear-projection experiment configuration."""

    missing = sorted(REQUIRED_CONFIG_KEYS.difference(config))
    if missing:
        raise ValueError(f"Phase 3B config is missing required keys: {missing}")
    _require(config["dataset_track"] == "jump_cpjump1_profiles", "dataset_track is unsupported.")
    _validate_output_root(config["output_root"])
    _validate_splits(config)
    _validate_seeds(config["seeds"])
    _validate_top_k(config["top_k"])
    _validate_preprocessing(config["preprocessing"])
    _validate_query_text(config["query_text"])
    _validate_metrics(config["metrics"])
    _validate_controls(config["controls"])
    _validate_artifact_policy(config["artifact_policy"])
    if int(config["minimum_evaluable_queries"]) <= 0:
        raise ValueError("minimum_evaluable_queries must be positive.")
    if config["aggregation"] != "perturbation_level":
        raise ValueError("aggregation must be perturbation_level.")
    return config


def _validate_splits(config: dict[str, Any]) -> None:
    primary = config["primary_split"]
    secondary = config["secondary_splits"]
    unavailable = config.get("unavailable_splits", {})
    if primary not in SUPPORTED_SPLITS:
        raise ValueError(f"Unsupported primary split: {primary}")
    if not isinstance(secondary, list):
        raise ValueError("secondary_splits must be a list.")
    unsupported = sorted(set(secondary).difference(SUPPORTED_SPLITS))
    if unsupported:
        raise ValueError(f"Unsupported secondary split names: {unsupported}")
    unsupported_unavailable = sorted(set(unavailable).difference(SUPPORTED_UNAVAILABLE_SPLITS))
    if unsupported_unavailable:
        raise ValueError(f"Unsupported unavailable split names: {unsupported_unavailable}")
    if "held_out_batch" in unavailable and "reason" not in unavailable["held_out_batch"]:
        raise ValueError("held_out_batch unavailability must include a reason.")


def _validate_seeds(seeds: Any) -> None:
    if not isinstance(seeds, list) or len(seeds) < 3:
        raise ValueError("seeds must list at least three deterministic seeds.")
    if any(not isinstance(seed, int) or seed < 0 for seed in seeds):
        raise ValueError("seeds must be non-negative integers.")
    if len(set(seeds)) != len(seeds):
        raise ValueError("seeds must be unique.")


def _validate_top_k(top_k: Any) -> None:
    if not isinstance(top_k, list) or not top_k:
        raise ValueError("top_k must be a non-empty list.")
    if any(not isinstance(k, int) or k <= 0 for k in top_k):
        raise ValueError("top_k values must be positive integers.")
    if sorted(top_k) != top_k or len(set(top_k)) != len(top_k):
        raise ValueError("top_k must be sorted and unique.")


def _validate_preprocessing(preprocessing: Any) -> None:
    if not isinstance(preprocessing, dict):
        raise ValueError("preprocessing must be a mapping.")
    required = {
        "feature_policy",
        "imputation",
        "scaling",
        "fit_scope",
        "near_zero_variance_threshold",
    }
    missing = sorted(required.difference(preprocessing))
    if missing:
        raise ValueError(f"preprocessing is missing required keys: {missing}")
    _require(
        preprocessing["feature_policy"] == "cell_painting_numeric_only",
        "preprocessing.feature_policy is unsupported.",
    )
    _require(preprocessing["imputation"] == "median", "preprocessing.imputation is unsupported.")
    _require(preprocessing["scaling"] == "standard", "preprocessing.scaling is unsupported.")
    _require(
        preprocessing["fit_scope"] == "train_only",
        "preprocessing.fit_scope must be train_only.",
    )
    if float(preprocessing["near_zero_variance_threshold"]) < 0:
        raise ValueError("near_zero_variance_threshold must be non-negative.")


def _validate_query_text(query_text: Any) -> None:
    if not isinstance(query_text, dict):
        raise ValueError("query_text must be a mapping.")
    allowed = set(query_text.get("allowed_fields", []))
    prohibited = set(query_text.get("prohibited_identifier_fields", []))
    if not allowed:
        raise ValueError("query_text.allowed_fields must not be empty.")
    overlap = sorted(allowed.intersection(prohibited))
    if overlap:
        raise ValueError(f"Prohibited identifier fields cannot be allowed query fields: {overlap}")


def _validate_metrics(metrics: Any) -> None:
    if not isinstance(metrics, list):
        raise ValueError("metrics must be a list.")
    missing = sorted(REQUIRED_METRICS.difference(metrics))
    if missing:
        raise ValueError(f"metrics is missing required metrics: {missing}")


def _validate_controls(controls: Any) -> None:
    if not isinstance(controls, list):
        raise ValueError("controls must be a list.")
    unsupported = sorted(set(controls).difference(SUPPORTED_CONTROLS))
    if unsupported:
        raise ValueError(f"Unsupported controls: {unsupported}")


def _validate_artifact_policy(policy: Any) -> None:
    if not isinstance(policy, dict):
        raise ValueError("artifact_policy must be a mapping.")
    for key in ["commit_generated_outputs", "commit_embeddings", "commit_model_weights"]:
        if policy.get(key) is not False:
            raise ValueError(f"artifact_policy.{key} must be false.")


def _validate_output_root(output_root: str) -> None:
    path = Path(output_root)
    parts = [part for part in path.parts if part not in {"", "."}]
    allowed = any(part in IGNORED_OUTPUT_ROOTS for part in parts) if path.is_absolute() else (
        bool(parts) and parts[0] in IGNORED_OUTPUT_ROOTS
    )
    if not allowed:
        raise ValueError(
            "output_root must be under an ignored local artifact directory: "
            f"{sorted(IGNORED_OUTPUT_ROOTS)}"
        )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)
