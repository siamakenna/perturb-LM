"""Controlled Phase 3C text-to-morphology alignment utilities."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge
from sklearn.metrics import average_precision_score
from sklearn.metrics.pairwise import cosine_similarity

from perturb_lm.data.jump import CELL_PAINTING_FEATURE_PREFIXES
from perturb_lm.modeling.preprocessing import (
    IGNORED_OUTPUT_ROOTS,
    MorphologyPreprocessor,
    _validate_ignored_output_path,
)
from perturb_lm.modeling.text_encoder import (
    BIOMEDBERT_SPEC,
    DeterministicFakeTextEncoder,
    TextEncoder,
    l2_normalize,
    validate_embedding_matrix,
)

ALLOWED_IDENTIFIER_STRIPPED_QUERY_FIELDS = [
    "Metadata_gene",
    "Metadata_pert_type",
    "Metadata_control_type",
    "Metadata_negcon_control_type",
]
PROHIBITED_QUERY_FIELDS = [
    "Metadata_target_sequence",
    "Metadata_broad_sample",
    "Metadata_pert_iname",
    "Metadata_pert_id",
    "Metadata_smiles",
    "Metadata_InChIKey",
    "Metadata_Plate",
    "Metadata_Well",
    "Metadata_Batch",
    "Metadata_Inferred_Batch",
    "profile_id",
    "source_profile_file",
    "source_profile_row",
]
DEFAULT_TOP_K = [1, 5, 10]
PHASE3C_METHODS = [
    "random",
    "shuffled_label",
    "identifier_stripped_tfidf",
    "frozen_text_embeddings_unaligned",
    "frozen_text_embeddings_linear_projection",
]


@dataclass(frozen=True)
class Phase3CSplit:
    """Train/test split labels for a controlled Phase 3C condition."""

    name: str
    frame: pd.DataFrame
    warnings: tuple[str, ...] = ()


def build_identifier_stripped_query_table(
    profiles: pd.DataFrame,
    *,
    label_column: str = "treatment",
    query_id_prefix: str = "phase3c",
) -> pd.DataFrame:
    """Build unique treatment-level queries from allowed metadata fields only."""

    if label_column not in profiles.columns:
        raise ValueError(f"Missing label column: {label_column}")
    rows: list[dict[str, object]] = []
    work = profiles.copy()
    work[label_column] = work[label_column].astype(str)
    for label, group in work.groupby(label_column, sort=True):
        row = group.iloc[0]
        text_parts = [
            str(row[column]).strip()
            for column in ALLOWED_IDENTIFIER_STRIPPED_QUERY_FIELDS
            if column in row.index and _is_nonempty(row[column])
        ]
        if not text_parts:
            text_parts = ["cellular perturbation"]
        query_text = " ".join(dict.fromkeys(text_parts))
        rows.append(
            {
                "query_id": f"{query_id_prefix}::{_public_hash(label)}",
                "query_text": query_text,
                "target_label": str(label),
                "label_column": label_column,
                "allowed_text_field_count": int(len(text_parts)),
            }
        )
    queries = pd.DataFrame(rows).sort_values("query_id", kind="mergesort").reset_index(drop=True)
    validate_identifier_stripped_text(queries, profiles)
    return queries


def validate_identifier_stripped_text(
    queries: pd.DataFrame,
    profiles: pd.DataFrame | None = None,
    *,
    text_column: str = "query_text",
    extra_prohibited_values: list[str] | None = None,
) -> None:
    """Reject direct identifiers before text encoding."""

    if text_column not in queries.columns:
        raise ValueError(f"Missing text column: {text_column}")
    prohibited_values = set(_clean(value) for value in extra_prohibited_values or [])
    if profiles is not None:
        for column in PROHIBITED_QUERY_FIELDS:
            if column not in profiles.columns:
                continue
            prohibited_values.update(
                _clean(value)
                for value in profiles[column].dropna().astype(str)
                if len(_clean(value)) >= 4
            )
    prohibited_values = {value for value in prohibited_values if value}
    for text in queries[text_column].fillna("").astype(str):
        lowered = text.lower()
        if any(value in lowered for value in prohibited_values):
            raise ValueError("Identifier-stripped query text contains a prohibited value.")


def make_phase3c_split(
    profiles: pd.DataFrame,
    *,
    split_type: str,
    seed: int = 0,
    plate_column: str = "plate",
    well_column: str = "well",
    batch_column: str = "batch",
    treatment_column: str = "treatment",
) -> Phase3CSplit:
    """Create deterministic split labels for supported Phase 3C conditions."""

    frame = profiles.copy()
    warnings: list[str] = []
    if split_type == "held_out_batch":
        if batch_column not in frame.columns or frame[batch_column].nunique(dropna=True) < 2:
            frame["split"] = "unavailable"
            return Phase3CSplit(
                name=split_type,
                frame=frame,
                warnings=("Held-out batch is unavailable because fewer than two batches exist.",),
            )
    column_by_split = {
        "held_out_plate": plate_column,
        "held_out_well": well_column,
        "held_out_treatment": treatment_column,
        "held_out_batch": batch_column,
    }
    column = column_by_split.get(split_type)
    if column is None:
        raise ValueError(f"Unsupported split_type: {split_type}")
    if column not in frame.columns:
        raise ValueError(f"Missing split column for {split_type}: {column}")
    values = sorted(frame[column].dropna().astype(str).unique())
    if len(values) < 2:
        frame["split"] = "unavailable"
        return Phase3CSplit(
            name=split_type,
            frame=frame,
            warnings=(f"{split_type} is unavailable because fewer than two values exist.",),
        )
    rng = np.random.default_rng(seed)
    ordered = list(values)
    rng.shuffle(ordered)
    n_test = max(1, int(round(len(ordered) * 0.25)))
    test_values = set(ordered[:n_test])
    frame["split"] = np.where(frame[column].astype(str).isin(test_values), "test", "train")
    if split_type == "held_out_treatment":
        overlap = set(frame.loc[frame["split"] == "train", treatment_column].astype(str)).intersection(
            set(frame.loc[frame["split"] == "test", treatment_column].astype(str))
        )
        if overlap:
            raise ValueError("Held-out treatment split has train/test treatment overlap.")
    return Phase3CSplit(name=split_type, frame=frame, warnings=tuple(warnings))


def consensus_profiles(
    profiles: pd.DataFrame,
    *,
    feature_columns: list[str],
    treatment_column: str = "treatment",
    method: str = "mean",
    split_column: str | None = None,
    allowed_split: str | None = None,
) -> pd.DataFrame:
    """Construct mean or median consensus targets within the permitted partition."""

    if method not in {"mean", "median"}:
        raise ValueError("Consensus method must be 'mean' or 'median'.")
    work = profiles.copy()
    if split_column and allowed_split is not None:
        work = work[work[split_column].astype(str) == allowed_split].copy()
    if work.empty:
        raise ValueError("No rows are available for consensus construction.")
    grouped = work.groupby(treatment_column, sort=True)
    agg = grouped[feature_columns].mean() if method == "mean" else grouped[feature_columns].median()
    result = agg.reset_index()
    result["replicate_count"] = grouped.size().to_numpy(dtype=int)
    if split_column and allowed_split is not None:
        result[split_column] = allowed_split
    return result


def run_phase3c_alignment(
    profiles: pd.DataFrame,
    *,
    encoder: TextEncoder,
    split_type: str = "held_out_plate",
    retrieval_filter: str = "none",
    seed: int = 0,
    label_column: str = "treatment",
    feature_columns: list[str] | None = None,
    top_k: list[int] | None = None,
    alpha: float = 1.0,
    bootstrap_samples: int = 200,
) -> dict[str, Any]:
    """Run a controlled text-to-morphology comparison on an in-memory profile table."""

    top_k = sorted(set(top_k or DEFAULT_TOP_K))
    split = make_phase3c_split(profiles, split_type=split_type, seed=seed, treatment_column=label_column)
    if "test" not in set(split.frame["split"].astype(str)):
        return {
            "split": split_type,
            "retrieval_filter": retrieval_filter,
            "status": "unavailable",
            "warnings": list(split.warnings),
        }
    feature_columns = feature_columns or _detect_feature_columns(split.frame)
    if not feature_columns:
        raise ValueError("No morphology feature columns are available.")
    train = split.frame[split.frame["split"] == "train"].reset_index(drop=True)
    test = split.frame[split.frame["split"] == "test"].reset_index(drop=True)
    preprocessor = MorphologyPreprocessor().fit(
        train,
        feature_columns=feature_columns,
        fit_split="train",
    )
    train_y = preprocessor.transform(train)
    test_y = preprocessor.transform(test)
    all_queries = build_identifier_stripped_query_table(split.frame, label_column=label_column)
    query_lookup = all_queries.set_index("target_label")["query_text"].astype(str).to_dict()
    train_texts = [query_lookup[str(label)] for label in train[label_column].astype(str)]
    test_queries = test[["profile_id", label_column, "plate", "well", "batch"]].copy()
    test_queries["query_id"] = test_queries["profile_id"].map(lambda value: f"profile::{_public_hash(value)}")
    test_queries["query_text"] = [query_lookup[str(label)] for label in test[label_column].astype(str)]
    test_queries["target_label"] = test[label_column].astype(str).to_numpy()
    validate_identifier_stripped_text(test_queries, split.frame)

    train_x = encoder.encode(train_texts)
    test_x = encoder.encode(test_queries["query_text"].astype(str).tolist())
    validate_embedding_matrix(train_x, expected_dim=encoder.embedding_dimension)
    validate_embedding_matrix(test_x, expected_dim=encoder.embedding_dimension)

    candidate_texts = [query_lookup[str(label)] for label in test[label_column].astype(str)]
    tfidf_scores = _tfidf_scores(test_queries["query_text"].astype(str).tolist(), candidate_texts)
    rng = np.random.default_rng(seed)
    random_scores = rng.random((len(test_queries), len(test)))
    shuffled_labels = rng.permutation(test[label_column].astype(str).to_numpy())
    unaligned_scores = cosine_similarity(
        _fixed_random_projection(test_x, test_y.shape[1], seed=seed),
        test_y,
    )
    projection = Ridge(alpha=alpha, fit_intercept=True)
    projection.fit(train_x, train_y)
    projected_scores = cosine_similarity(projection.predict(test_x), test_y)

    modes = {
        "random": (random_scores, test[label_column].astype(str).to_numpy()),
        "shuffled_label": (tfidf_scores, shuffled_labels),
        "identifier_stripped_tfidf": (tfidf_scores, test[label_column].astype(str).to_numpy()),
        "frozen_text_embeddings_unaligned": (
            unaligned_scores,
            test[label_column].astype(str).to_numpy(),
        ),
        "frozen_text_embeddings_linear_projection": (
            projected_scores,
            test[label_column].astype(str).to_numpy(),
        ),
    }
    per_query = pd.concat(
        [
            score_profile_queries(
                test_queries,
                test,
                scores,
                candidate_labels=labels,
                label_column=label_column,
                top_k=top_k,
                mode=mode,
                retrieval_filter=retrieval_filter,
            )
            for mode, (scores, labels) in modes.items()
        ],
        ignore_index=True,
    )
    summary = summarize_phase3c_per_query(
        per_query,
        top_k=top_k,
        bootstrap_samples=bootstrap_samples,
    )
    return {
        "split": split_type,
        "retrieval_filter": retrieval_filter,
        "status": "completed",
        "seed": seed,
        "train_profiles": int(len(train)),
        "test_profiles": int(len(test)),
        "train_treatments": int(train[label_column].nunique(dropna=True)),
        "test_treatments": int(test[label_column].nunique(dropna=True)),
        "feature_count": int(len(preprocessor.feature_columns_)),
        "text_embedding_dimension": int(encoder.embedding_dimension),
        "projection_type": "ridge_regression",
        "regularization_alpha": float(alpha),
        "preprocessing_fit_scope": preprocessor.fit_metadata_["fit_split"],
        "per_query": per_query,
        "summary": summary,
        "split_checksum": _aggregate_checksum(split.frame, split_column="split"),
        "warnings": list(split.warnings),
    }


def score_profile_queries(
    queries: pd.DataFrame,
    candidates: pd.DataFrame,
    scores: np.ndarray,
    *,
    candidate_labels: np.ndarray,
    label_column: str,
    top_k: list[int],
    mode: str,
    retrieval_filter: str,
) -> pd.DataFrame:
    """Score profile-originated queries after perturbation-level score aggregation."""

    rows: list[dict[str, object]] = []
    candidate_labels = np.asarray(candidate_labels, dtype=str)
    for query_index, query in queries.reset_index(drop=True).iterrows():
        mask = np.ones(len(candidates), dtype=bool)
        if retrieval_filter in {"exclude_same_plate", "exclude_same_plate_and_well"}:
            mask &= candidates["plate"].astype(str).to_numpy() != str(query["plate"])
        if retrieval_filter in {"exclude_same_well", "exclude_same_plate_and_well"}:
            mask &= candidates["well"].astype(str).to_numpy() != str(query["well"])
        if retrieval_filter not in {
            "none",
            "exclude_same_plate",
            "exclude_same_well",
            "exclude_same_plate_and_well",
        }:
            raise ValueError(f"Unsupported retrieval_filter: {retrieval_filter}")
        target = str(query["target_label"])
        labels = candidate_labels[mask]
        candidate_scores = scores[query_index, mask]
        candidate_frame = candidates.loc[mask].reset_index(drop=True)
        positives = labels == target
        if len(labels):
            aggregated = _aggregate_by_treatment(labels, candidate_scores)
            ordered_treatments = sorted(aggregated, key=aggregated.get, reverse=True)
            y_true = np.array([label == target for label in aggregated], dtype=int)
            y_score = np.array([aggregated[label] for label in aggregated], dtype=float)
        else:
            ordered_treatments = []
            y_true = np.array([], dtype=int)
            y_score = np.array([], dtype=float)
        top_profile_index = int(np.argmax(candidate_scores)) if len(candidate_scores) else None
        top_profile = candidate_frame.iloc[top_profile_index] if top_profile_index is not None else {}
        row: dict[str, object] = {
            "mode": mode,
            "query_id": query["query_id"],
            "n_positives": int(positives.sum()),
            "average_precision": (
                float(average_precision_score(y_true, y_score)) if y_true.any() else np.nan
            ),
            "same_plate_at_1": float(str(top_profile.get("plate", "")) == str(query["plate"]))
            if len(candidate_scores)
            else np.nan,
            "same_well_at_1": float(str(top_profile.get("well", "")) == str(query["well"]))
            if len(candidate_scores)
            else np.nan,
            "same_batch_at_1": float(str(top_profile.get("batch", "")) == str(query["batch"]))
            if len(candidate_scores)
            else np.nan,
            "same_treatment_at_1": float(
                str(top_profile.get(label_column, "")) == str(query["target_label"])
            )
            if len(candidate_scores)
            else np.nan,
        }
        for k in top_k:
            row[f"hit_at_{k}"] = float(target in ordered_treatments[:k]) if y_true.any() else np.nan
            row[f"recall_at_{k}"] = row[f"hit_at_{k}"]
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_phase3c_per_query(
    per_query: pd.DataFrame,
    *,
    top_k: list[int],
    bootstrap_samples: int = 200,
) -> pd.DataFrame:
    """Summarize Phase 3C metrics and paired deltas against TF-IDF."""

    metric_columns = [
        "average_precision",
        *[f"hit_at_{k}" for k in top_k],
        *[f"recall_at_{k}" for k in top_k],
        "same_plate_at_1",
        "same_well_at_1",
        "same_batch_at_1",
        "same_treatment_at_1",
    ]
    rows: list[dict[str, object]] = []
    rng = np.random.default_rng(0)
    for mode, group in per_query.groupby("mode", sort=False):
        evaluable = group[group["n_positives"] > 0]
        for metric in metric_columns:
            if metric not in group:
                continue
            values = evaluable[metric].to_numpy(dtype=float)
            finite = values[np.isfinite(values)]
            estimate, ci_low, ci_high = _bootstrap_mean(finite, rng, bootstrap_samples)
            rows.append(
                {
                    "mode": mode,
                    "comparison": "point_estimate",
                    "metric": metric,
                    "n_total_queries": int(len(group)),
                    "n_evaluable_queries": int(len(evaluable)),
                    "estimate": estimate,
                    "ci95_low": ci_low,
                    "ci95_high": ci_high,
                }
            )
    reference = per_query[per_query["mode"] == "identifier_stripped_tfidf"]
    for mode, group in per_query.groupby("mode", sort=False):
        if mode == "identifier_stripped_tfidf":
            continue
        merged = group.merge(reference, on="query_id", suffixes=("", "_reference"))
        evaluable = merged[(merged["n_positives"] > 0) & (merged["n_positives_reference"] > 0)]
        for metric in metric_columns:
            ref_metric = f"{metric}_reference"
            if metric not in evaluable or ref_metric not in evaluable:
                continue
            values = (
                evaluable[metric].to_numpy(dtype=float)
                - evaluable[ref_metric].to_numpy(dtype=float)
            )
            finite = values[np.isfinite(values)]
            estimate, ci_low, ci_high = _bootstrap_mean(finite, rng, bootstrap_samples)
            rows.append(
                {
                    "mode": mode,
                    "comparison": "paired_difference_vs_identifier_stripped_tfidf",
                    "metric": metric,
                    "n_total_queries": int(len(merged)),
                    "n_evaluable_queries": int(len(evaluable)),
                    "estimate": estimate,
                    "ci95_low": ci_low,
                    "ci95_high": ci_high,
                }
            )
    return pd.DataFrame(rows)


def write_phase3c_public_safe_summary(result: dict[str, Any], out: Path | str) -> None:
    """Write aggregate-only Phase 3C summaries under ignored output paths."""

    path = Path(out)
    _validate_ignored_output_path(path)
    path.mkdir(parents=True, exist_ok=True)
    summary = result["summary"].copy()
    summary.to_csv(path / "phase3c_alignment_summary.csv", index=False)
    payload = {
        "encoder": BIOMEDBERT_SPEC.__dict__,
        "split": result["split"],
        "retrieval_filter": result["retrieval_filter"],
        "status": result["status"],
        "seed": result["seed"],
        "train_profiles": result["train_profiles"],
        "test_profiles": result["test_profiles"],
        "train_treatments": result["train_treatments"],
        "test_treatments": result["test_treatments"],
        "feature_count": result["feature_count"],
        "text_embedding_dimension": result["text_embedding_dimension"],
        "projection_type": result["projection_type"],
        "regularization_alpha": result["regularization_alpha"],
        "split_checksum": result["split_checksum"],
        "warnings": result["warnings"],
        "scientific_caution": (
            "Synthetic or first-pass Phase 3C outputs are controlled retrieval benchmark "
            "artifacts and are not biological retrieval evidence by themselves."
        ),
    }
    (path / "phase3c_public_safe_manifest.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )


def run_synthetic_phase3c_alignment_smoke(
    *,
    out_dir: Path | str = Path("outputs/phase3c_alignment_smoke"),
    seed: int = 0,
) -> dict[str, Any]:
    """Run a deterministic, learnable synthetic Phase 3C alignment smoke test."""

    profiles, feature_columns = make_synthetic_phase3c_profiles(seed=seed)
    encoder = LinearSyntheticTextEncoder(seed=seed)
    result = run_phase3c_alignment(
        profiles,
        encoder=encoder,
        split_type="held_out_treatment",
        retrieval_filter="exclude_same_plate_and_well",
        seed=seed,
        feature_columns=feature_columns,
        bootstrap_samples=100,
    )
    write_phase3c_public_safe_summary(result, out_dir)
    return result


def make_synthetic_phase3c_profiles(
    *,
    seed: int = 0,
    n_treatments: int = 24,
    replicates_per_treatment: int = 4,
    text_dim: int = 12,
    profile_dim: int = 8,
) -> tuple[pd.DataFrame, list[str]]:
    """Create synthetic profiles with a learnable text-to-morphology relationship."""

    rng = np.random.default_rng(seed)
    rows: list[dict[str, object]] = []
    for treatment_index in range(n_treatments):
        gene = f"gene_group_{treatment_index % 8}"
        pert_type = "crispr" if treatment_index % 2 else "compound"
        text = f"{gene} {pert_type}"
        text_vec = LinearSyntheticTextEncoder(seed=seed, embedding_dimension_value=text_dim).encode([text])[0]
        projection = _synthetic_projection(text_dim, profile_dim, seed)
        center = text_vec @ projection
        for replicate in range(replicates_per_treatment):
            plate_group = replicate % 4
            row: dict[str, object] = {
                "profile_id": f"profile-{treatment_index}-{replicate}",
                "treatment": f"synthetic-treatment-{treatment_index}",
                "plate": f"plate-{plate_group}",
                "well": f"{chr(65 + replicate)}{(treatment_index % 12) + 1:02d}",
                "batch": "batch-0",
                "Metadata_gene": gene,
                "Metadata_pert_type": pert_type,
                "Metadata_control_type": "",
                "Metadata_negcon_control_type": "",
                "Metadata_target_sequence": f"forbidden-sequence-{treatment_index}",
                "Metadata_broad_sample": f"forbidden-sample-{treatment_index}",
            }
            values = center + rng.normal(scale=0.03, size=profile_dim)
            row.update({f"Cells_feature_{idx:03d}": values[idx] for idx in range(profile_dim)})
            rows.append(row)
    feature_columns = [f"Cells_feature_{idx:03d}" for idx in range(profile_dim)]
    return pd.DataFrame(rows), feature_columns


class LinearSyntheticTextEncoder(DeterministicFakeTextEncoder):
    """Fake encoder that shares the deterministic projection used by synthetic profiles."""

    def __init__(self, *, seed: int = 0, embedding_dimension_value: int = 12) -> None:
        super().__init__(
            embedding_dimension_value=embedding_dimension_value,
            seed=seed,
            normalize=False,
        )


def _tfidf_scores(query_texts: list[str], candidate_texts: list[str]) -> np.ndarray:
    try:
        matrix = TfidfVectorizer(lowercase=True, ngram_range=(1, 2)).fit_transform(
            [*query_texts, *candidate_texts]
        )
    except ValueError:
        return np.zeros((len(query_texts), len(candidate_texts)), dtype=float)
    return cosine_similarity(matrix[: len(query_texts)], matrix[len(query_texts) :])


def _fixed_random_projection(text_embeddings: np.ndarray, output_dim: int, *, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    weights = rng.normal(scale=1.0 / np.sqrt(text_embeddings.shape[1]), size=(text_embeddings.shape[1], output_dim))
    return l2_normalize(text_embeddings @ weights)


def _synthetic_projection(input_dim: int, output_dim: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed + 991)
    return rng.normal(scale=1.0 / np.sqrt(input_dim), size=(input_dim, output_dim))


def _aggregate_by_treatment(labels: np.ndarray, scores: np.ndarray) -> dict[str, float]:
    aggregated: dict[str, float] = {}
    for label, score in zip(labels, scores, strict=True):
        label = str(label)
        aggregated[label] = max(float(score), aggregated.get(label, -np.inf))
    return aggregated


def _bootstrap_mean(
    values: np.ndarray,
    rng: np.random.Generator,
    bootstrap_samples: int,
) -> tuple[float, float, float]:
    finite = values[np.isfinite(values)]
    if len(finite) == 0:
        return np.nan, np.nan, np.nan
    boot = np.array(
        [
            float(np.mean(rng.choice(finite, size=len(finite), replace=True)))
            for _ in range(max(bootstrap_samples, 1))
        ]
    )
    low, high = np.quantile(boot, [0.025, 0.975])
    return float(np.mean(finite)), float(low), float(high)


def _detect_feature_columns(frame: pd.DataFrame) -> list[str]:
    return sorted(
        str(column)
        for column in frame.columns
        if str(column).startswith(CELL_PAINTING_FEATURE_PREFIXES)
        and pd.api.types.is_numeric_dtype(frame[column])
    )


def _aggregate_checksum(frame: pd.DataFrame, *, split_column: str) -> str:
    payload = {
        "n_rows": int(len(frame)),
        "split_counts": frame[split_column].astype(str).value_counts().sort_index().to_dict(),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _public_hash(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]


def _clean(value: object) -> str:
    return str(value).strip().lower()


def _is_nonempty(value: object) -> bool:
    if pd.isna(value):
        return False
    text = str(value).strip().lower()
    return text not in {"", "nan", "none", "null", "<na>"}
