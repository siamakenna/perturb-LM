"""Synthetic linear-projection contract for future text-profile alignment."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.metrics import average_precision_score
from sklearn.metrics.pairwise import cosine_similarity

from perturb_lm.engineering.runtime import (
    PipelineRuntimeLogger,
    dashboard_safe_runtime_summary,
    write_runtime_log,
)
from perturb_lm.modeling.preprocessing import (
    IGNORED_OUTPUT_ROOTS,
    MorphologyPreprocessor,
)


@dataclass
class LinearProjectionContract:
    """Small sklearn-compatible linear projection wrapper."""

    alpha: float = 1e-6
    model: Ridge | None = None
    input_dim_: int | None = None
    output_dim_: int | None = None
    fit_metadata_: dict[str, Any] | None = None

    def fit(
        self,
        text_embeddings: np.ndarray,
        morphology_targets: np.ndarray,
        *,
        fit_split: str = "train",
    ) -> LinearProjectionContract:
        if text_embeddings.shape[0] != morphology_targets.shape[0]:
            raise ValueError("Text and morphology training rows must align.")
        self.model = Ridge(alpha=self.alpha, fit_intercept=True)
        self.model.fit(text_embeddings, morphology_targets)
        self.input_dim_ = int(text_embeddings.shape[1])
        self.output_dim_ = int(morphology_targets.shape[1])
        self.fit_metadata_ = {
            "fit_split": fit_split,
            "n_fit_rows": int(text_embeddings.shape[0]),
            "input_dim": self.input_dim_,
            "output_dim": self.output_dim_,
        }
        return self

    def transform(self, text_embeddings: np.ndarray) -> np.ndarray:
        if self.model is None:
            raise ValueError("LinearProjectionContract must be fitted before transform.")
        if text_embeddings.shape[1] != self.input_dim_:
            raise ValueError("Text embedding dimension does not match fitted projection.")
        return np.asarray(self.model.predict(text_embeddings), dtype=float)

    def save(self, path: Path | str) -> None:
        path = Path(path)
        _validate_ignored_output_path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            path,
            coef=self.model.coef_ if self.model is not None else np.empty((0, 0)),
            intercept=self.model.intercept_ if self.model is not None else np.empty(0),
            input_dim=self.input_dim_,
            output_dim=self.output_dim_,
            alpha=self.alpha,
        )


def load_linear_projection_contract(path: Path | str) -> LinearProjectionContract:
    """Reload a saved synthetic projection contract."""

    archive = np.load(path, allow_pickle=False)
    contract = LinearProjectionContract(alpha=float(archive["alpha"]))
    model = Ridge(alpha=contract.alpha, fit_intercept=True)
    model.coef_ = archive["coef"]
    model.intercept_ = archive["intercept"]
    model.n_features_in_ = int(archive["input_dim"])
    contract.model = model
    contract.input_dim_ = int(archive["input_dim"])
    contract.output_dim_ = int(archive["output_dim"])
    contract.fit_metadata_ = {
        "fit_split": "train",
        "input_dim": contract.input_dim_,
        "output_dim": contract.output_dim_,
    }
    return contract


def make_synthetic_projection_fixture(
    *,
    seed: int = 0,
    learnable: bool = True,
    n_treatments: int = 18,
    replicates_per_treatment: int = 4,
    text_dim: int = 8,
    profile_dim: int = 6,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create deterministic synthetic text embeddings and morphology profiles."""

    rng = np.random.default_rng(seed)
    text = rng.normal(size=(n_treatments, text_dim))
    true_projection = rng.normal(size=(text_dim, profile_dim))
    if learnable:
        centers = text @ true_projection
    else:
        centers = rng.normal(size=(n_treatments, profile_dim))
    rows: list[dict[str, object]] = []
    for treatment_index in range(n_treatments):
        split = _split_for_treatment(treatment_index, n_treatments)
        for replicate_index in range(replicates_per_treatment):
            noise = rng.normal(scale=0.02, size=profile_dim)
            profile = centers[treatment_index] + noise
            row: dict[str, object] = {
                "profile_id": f"profile-{treatment_index}-{replicate_index}",
                "treatment": f"treatment-{treatment_index}",
                "split": split,
                "plate": f"plate-{treatment_index % 6}",
                "well": f"A{replicate_index + 1:02d}",
            }
            row.update({f"Cells_feature_{idx:03d}": profile[idx] for idx in range(profile_dim)})
            rows.append(row)
    profiles = pd.DataFrame(rows)
    text_rows = [
        {
            "query_id": f"query-{idx}",
            "treatment": f"treatment-{idx}",
            "split": _split_for_treatment(idx, n_treatments),
            **{f"text_{dim:03d}": text[idx, dim] for dim in range(text_dim)},
        }
        for idx in range(n_treatments)
    ]
    return profiles, pd.DataFrame(text_rows)


def run_synthetic_projection_contract(
    *,
    out_dir: Path | str = Path("outputs/phase3b_projection_smoke"),
    seed: int = 0,
    learnable: bool = True,
) -> dict[str, Any]:
    """Run the synthetic projection smoke workflow and write safe aggregate outputs."""

    out = Path(out_dir)
    _validate_ignored_output_path(out)
    out.mkdir(parents=True, exist_ok=True)
    runtime = PipelineRuntimeLogger(
        dataset_track="synthetic_phase3b_contract",
        seed=seed,
        split_name="held_out_treatment",
    )
    with runtime.stage("data_loading"):
        profiles, text_queries = make_synthetic_projection_fixture(
            seed=seed,
            learnable=learnable,
        )
    with runtime.stage("schema_validation"):
        feature_columns = [
            column for column in profiles.columns if column.startswith("Cells_feature_")
        ]
        text_columns = [
            column for column in text_queries.columns if column.startswith("text_")
        ]

    with runtime.stage("split_generation"):
        train_profiles = profiles[profiles["split"] == "train"].reset_index(drop=True)
        test_profiles = profiles[profiles["split"] == "test"].reset_index(drop=True)
        train_queries = text_queries[text_queries["split"] == "train"].reset_index(drop=True)
        test_queries = text_queries[text_queries["split"] == "test"].reset_index(drop=True)
        train_text_lookup = train_queries.set_index("treatment")[text_columns]
        train_text = np.vstack(
            [
                train_text_lookup.loc[treatment].to_numpy(dtype=float)
                for treatment in train_profiles["treatment"]
            ]
        )

    with runtime.stage("preprocessing_fit"):
        preprocessor = MorphologyPreprocessor().fit(
            train_profiles,
            feature_columns=feature_columns,
            fit_split="train",
        )
    with runtime.stage("preprocessing_transform"):
        train_targets = preprocessor.transform(train_profiles)
        test_targets = preprocessor.transform(test_profiles)
    with runtime.stage("baseline_fitting"):
        projection = LinearProjectionContract().fit(
            train_text,
            train_targets,
            fit_split="train",
        )
    with runtime.stage("retrieval"):
        test_text = test_queries[text_columns].to_numpy(dtype=float)
        projected = projection.transform(test_text)
        projection_summary = score_projected_perturbation_retrieval(
            projected,
            test_targets,
            query_treatments=test_queries["treatment"].astype(str).tolist(),
            candidate_treatments=test_profiles["treatment"].astype(str).tolist(),
            top_k=[1, 5, 10],
        )
        random_summary = score_projected_perturbation_retrieval(
            np.random.default_rng(seed).normal(size=projected.shape),
            test_targets,
            query_treatments=test_queries["treatment"].astype(str).tolist(),
            candidate_treatments=test_profiles["treatment"].astype(str).tolist(),
            top_k=[1, 5, 10],
        )
    summary = {
        "dataset": "synthetic_phase3b_contract",
        "seed": seed,
        "learnable": learnable,
        "train_rows": int(len(train_profiles)),
        "validation_rows": int((profiles["split"] == "validation").sum()),
        "test_rows": int(len(test_profiles)),
        "text_embedding_dim": int(len(text_columns)),
        "profile_embedding_dim": int(len(preprocessor.feature_columns_)),
        "projection": projection_summary,
        "random": random_summary,
        "preprocessing_fit_scope": preprocessor.fit_metadata_["fit_split"],
        "projection_fit_scope": projection.fit_metadata_["fit_split"],
        "artifact_policy": (
            "Generated weights, preprocessors, and summaries stay under ignored outputs."
        ),
    }
    with runtime.stage("report_generation"):
        projection.save(out / "synthetic_linear_projection_weights.npz")
        preprocessor.save(out / "synthetic_morphology_preprocessor.pkl")
        (out / "phase3b_projection_smoke_summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n"
        )
    runtime_payload = runtime.finish()
    write_runtime_log(out / "runtime_log.json", runtime_payload)
    write_runtime_log(
        out / "runtime_dashboard_safe.json",
        dashboard_safe_runtime_summary(runtime_payload),
    )
    return summary


def score_projected_perturbation_retrieval(
    query_embeddings: np.ndarray,
    candidate_profiles: np.ndarray,
    *,
    query_treatments: list[str],
    candidate_treatments: list[str],
    top_k: list[int],
) -> dict[str, float]:
    """Score projected text-to-profile retrieval after perturbation-level aggregation."""

    scores = cosine_similarity(query_embeddings, candidate_profiles)
    unique_treatments = sorted(set(candidate_treatments))
    rows = []
    for query_index, treatment in enumerate(query_treatments):
        perturbation_scores = {
            candidate_treatment: float(
                np.max(
                    scores[
                        query_index,
                        [
                            idx
                            for idx, label in enumerate(candidate_treatments)
                            if label == candidate_treatment
                        ],
                    ]
                )
            )
            for candidate_treatment in unique_treatments
        }
        ordered = sorted(perturbation_scores, key=perturbation_scores.get, reverse=True)
        y_true = np.array([candidate == treatment for candidate in unique_treatments], dtype=int)
        y_score = np.array([perturbation_scores[candidate] for candidate in unique_treatments])
        rows.append(
            {
                "average_precision": float(average_precision_score(y_true, y_score)),
                **{f"hit_at_{k}": float(treatment in ordered[:k]) for k in top_k},
                **{f"recall_at_{k}": float(treatment in ordered[:k]) for k in top_k},
            }
        )
    frame = pd.DataFrame(rows)
    summary: dict[str, float] = {
        "n_total_queries": float(len(frame)),
        "n_evaluable_queries": float(len(frame)),
        "mean_average_precision": float(frame["average_precision"].mean()),
    }
    for k in top_k:
        if f"hit_at_{k}" in frame:
            summary[f"hit_at_{k}"] = float(frame[f"hit_at_{k}"].mean())
            summary[f"recall_at_{k}"] = float(frame[f"recall_at_{k}"].mean())
    return summary


def _split_for_treatment(index: int, n_treatments: int) -> str:
    if index >= int(n_treatments * 0.8):
        return "test"
    if index >= int(n_treatments * 0.65):
        return "validation"
    return "train"


def _validate_ignored_output_path(path: Path) -> None:
    parts = [part for part in path.parts if part not in {".", ""}]
    if path.is_absolute():
        allowed = any(part in IGNORED_OUTPUT_ROOTS for part in parts)
    else:
        allowed = bool(parts) and parts[0] in IGNORED_OUTPUT_ROOTS
    if not allowed:
        raise ValueError(
            "Synthetic projection artifacts must be written under ignored output directories."
        )
