"""Metadata-derived text-to-profile retrieval baselines for JUMP profiles."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import average_precision_score
from sklearn.metrics.pairwise import cosine_similarity

from perturb_lm.data.jump import (
    LOCAL_ONLY_NOTE,
    add_jump_profile_ids,
    detect_jump_profile_schema,
    load_jump_profile_tables,
)

NULL_LABELS = {"", "nan", "none", "null", "<na>"}
TEXT_COLUMN_CANDIDATES = [
    "Metadata_broad_sample",
    "Metadata_pert_iname",
    "Metadata_gene",
    "Metadata_pert_type",
    "Metadata_control_type",
    "Metadata_smiles",
    "Metadata_InChIKey",
    "Metadata_target_sequence",
]
IDENTIFIER_STRIPPED_TEXT_COLUMN_CANDIDATES = [
    "Metadata_gene",
    "Metadata_pert_type",
    "Metadata_control_type",
    "Metadata_target_sequence",
    "Metadata_negcon_control_type",
]


def build_metadata_text_queries(
    profiles: pd.DataFrame,
    *,
    label_column: str,
    query_limit: int | None = None,
) -> pd.DataFrame:
    """Build auditable text queries from profile metadata labels."""

    rows: list[dict[str, object]] = []
    work = profiles.copy()
    work[label_column] = work[label_column].map(_clean_label)
    work = work[_valid_label_mask(work[label_column])]
    for label, group in work.groupby(label_column, sort=True):
        row = group.iloc[0]
        pert_name = _first_nonempty(row, ["Metadata_pert_iname", "Metadata_broad_sample"])
        gene = _first_nonempty(row, ["Metadata_gene"])
        pert_type = _first_nonempty(row, ["Metadata_pert_type"]) or "unknown"
        if _is_nonempty(pert_name):
            query_text = f"cells treated with {pert_name}"
            target_name = pert_name
        elif _is_nonempty(gene):
            query_text = f"cells with perturbation of {gene}"
            target_name = gene
        else:
            query_text = f"cells with perturbation label {label}"
            target_name = label
        if _is_nonempty(gene):
            mechanism_query_text = f"cells with perturbation of {gene}"
        elif _is_nonempty(pert_type):
            mechanism_query_text = f"cells with perturbation type {pert_type}"
        else:
            mechanism_query_text = "cells with perturbation"
        rows.append(
            {
                "query_id": f"jump_metadata::{label}",
                "query_text": query_text,
                "mechanism_query_text": mechanism_query_text,
                "target_label": label,
                "target_name": target_name,
                "target_type": pert_type,
                "label_column": label_column,
                "n_target_profiles": int(len(group)),
            }
        )
        if query_limit is not None and len(rows) >= query_limit:
            break
    return pd.DataFrame(rows)


def run_text_profile_retrieval(
    data_root: Path | str = Path("data/raw/jump_pilot"),
    *,
    queries: pd.DataFrame | None = None,
    label_column: str | None = None,
    profile_files: list[Path | str] | None = None,
    max_rows: int | None = None,
    query_limit: int | None = None,
    top_k: list[int] | None = None,
    seed: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Run a simple text-to-profile metadata baseline and controls."""

    top_k = sorted(set(top_k or [1, 5, 10]))
    if not top_k or min(top_k) <= 0:
        raise ValueError("top_k must contain positive integers.")

    root = Path(data_root)
    profiles, loaded_paths, load_warnings = load_jump_profile_tables(
        root,
        profile_files=profile_files,
        max_rows=max_rows,
    )
    schema = detect_jump_profile_schema(profiles)
    warnings = [*load_warnings, *schema["warnings"]]
    detected_labels = schema["likely_perturbation_treatment_columns"]
    label_column = label_column or (detected_labels[0] if detected_labels else "")
    if not label_column or label_column not in profiles.columns:
        raise ValueError("No valid treatment label column is available for text retrieval.")

    indexed_profiles = add_jump_profile_ids(profiles, schema)
    text_columns = [
        column for column in TEXT_COLUMN_CANDIDATES if column in indexed_profiles.columns
    ]
    identifier_stripped_text_columns = [
        column
        for column in IDENTIFIER_STRIPPED_TEXT_COLUMN_CANDIDATES
        if column in indexed_profiles.columns
    ]
    if label_column not in text_columns:
        text_columns.insert(0, label_column)
    indexed_profiles["_candidate_text"] = indexed_profiles.apply(
        lambda row: _metadata_text(row, text_columns),
        axis=1,
    )
    indexed_profiles["_identifier_stripped_candidate_text"] = indexed_profiles.apply(
        lambda row: _metadata_text(row, identifier_stripped_text_columns),
        axis=1,
    )
    indexed_profiles["_target_label"] = indexed_profiles[label_column].map(_clean_label)
    indexed_profiles = indexed_profiles[_valid_label_mask(indexed_profiles["_target_label"])]

    if queries is None:
        queries = build_metadata_text_queries(
            indexed_profiles,
            label_column=label_column,
            query_limit=query_limit,
        )
    else:
        queries = queries.copy()
        if query_limit is not None:
            queries = queries.head(query_limit)
    _validate_queries(queries)

    if indexed_profiles.empty or queries.empty:
        raise ValueError("Text-to-profile retrieval requires non-empty profiles and queries.")

    query_texts = queries["query_text"].astype(str).tolist()
    mechanism_query_texts = _query_texts_for_identifier_stripped(queries)
    scores = _tfidf_scores(
        query_texts,
        indexed_profiles["_candidate_text"].astype(str).tolist(),
    )
    identifier_stripped_scores = _tfidf_scores(
        mechanism_query_texts,
        indexed_profiles["_identifier_stripped_candidate_text"].astype(str).tolist(),
    )

    labels = indexed_profiles["_target_label"].to_numpy(dtype=str)
    rng = np.random.default_rng(seed)
    random_scores = rng.random(scores.shape)
    shuffled_labels = rng.permutation(labels)
    modes = {
        "metadata_tfidf": (scores, labels, query_texts),
        "identifier_stripped_tfidf": (
            identifier_stripped_scores,
            labels,
            mechanism_query_texts,
        ),
        "random": (random_scores, labels, query_texts),
        "shuffled_label": (scores, shuffled_labels, query_texts),
    }
    per_query_rows: list[dict[str, object]] = []
    hit_rows: list[dict[str, object]] = []
    for mode, (mode_scores, mode_labels, mode_query_texts) in modes.items():
        mode_per_query, mode_hits = _score_queries(
            queries,
            indexed_profiles,
            mode_scores,
            mode_labels,
            scored_query_texts=mode_query_texts,
            top_k=top_k,
            mode=mode,
            schema=schema,
        )
        per_query_rows.extend(mode_per_query)
        hit_rows.extend(mode_hits)

    per_query = pd.DataFrame(per_query_rows)
    hits = pd.DataFrame(hit_rows)
    summary = summarize_text_profile_retrieval(per_query, top_k=top_k)
    metadata = {
        "dataset": "jump_pilot",
        "local_data_root": str(root),
        "input_profile_file_paths": [str(path) for path in loaded_paths],
        "number_of_profile_rows": int(len(indexed_profiles)),
        "number_of_queries": int(len(queries)),
        "label_column": label_column,
        "text_columns": text_columns,
        "identifier_stripped_text_columns": identifier_stripped_text_columns,
        "detected_batch_column": schema["likely_batch_column"],
        "detected_plate_column": schema["likely_plate_column"],
        "detected_well_column": schema["likely_well_column"],
        "modes": list(modes),
        "top_k": top_k,
        "warnings": [
            *warnings,
            (
                "This is a metadata-derived lexical text-to-profile baseline. It is useful "
                "as a control, but it is not a biological retrieval claim."
            ),
            (
                "metadata_tfidf includes direct perturbation identifiers. "
                "identifier_stripped_tfidf removes those identifiers from candidate text "
                "and should be interpreted as the tougher control."
            ),
        ],
        "local_only_note": LOCAL_ONLY_NOTE,
    }
    return per_query, hits, summary, metadata


def run_text_profile_retrieval_multi_seed(
    data_root: Path | str = Path("data/raw/jump_pilot"),
    *,
    queries: pd.DataFrame | None = None,
    label_column: str | None = None,
    profile_files: list[Path | str] | None = None,
    max_rows: int | None = None,
    query_limit: int | None = None,
    top_k: list[int] | None = None,
    seeds: list[int] | None = None,
    bootstrap_samples: int = 1000,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Run metadata controls across deterministic seeds and summarize stability."""

    seeds = seeds or [0, 1, 2, 3, 4]
    if len(seeds) < 3:
        raise ValueError("At least three seeds are required for multi-seed baselines.")
    if len(set(seeds)) != len(seeds) or any(seed < 0 for seed in seeds):
        raise ValueError("Seeds must be unique non-negative integers.")

    all_summary_rows: list[pd.DataFrame] = []
    metadata: dict[str, Any] | None = None
    for seed in seeds:
        _, _, summary, run_metadata = run_text_profile_retrieval(
            data_root,
            queries=queries,
            label_column=label_column,
            profile_files=profile_files,
            max_rows=max_rows,
            query_limit=query_limit,
            top_k=top_k,
            seed=seed,
        )
        seed_summary = summary.copy()
        seed_summary["seed"] = seed
        all_summary_rows.append(_with_enrichment_over_random(seed_summary))
        metadata = run_metadata

    by_seed = pd.concat(all_summary_rows, ignore_index=True)
    aggregate = summarize_multiseed_text_profile_retrieval(
        by_seed,
        bootstrap_samples=bootstrap_samples,
    )
    result_metadata = {
        **(metadata or {}),
        "seeds": seeds,
        "seed_count": len(seeds),
        "bootstrap_samples": bootstrap_samples,
        "warnings": [
            *((metadata or {}).get("warnings", [])),
            "Multi-seed summaries measure baseline stability, not model training success.",
        ],
    }
    return by_seed, aggregate, result_metadata


def summarize_text_profile_retrieval(per_query: pd.DataFrame, *, top_k: list[int]) -> pd.DataFrame:
    """Summarize text-to-profile retrieval rows by mode."""

    rows: list[dict[str, object]] = []
    for mode, group in per_query.groupby("mode", sort=False):
        evaluable = group[group["n_positives"] > 0]
        rows.extend(
            [
                {
                    "mode": mode,
                    "metric": "n_queries",
                    "value": int(len(group)),
                },
                {
                    "mode": mode,
                    "metric": "n_evaluable_queries",
                    "value": int(len(evaluable)),
                },
                {
                    "mode": mode,
                    "metric": "mean_average_precision",
                    "value": float(evaluable["average_precision"].mean())
                    if len(evaluable)
                    else np.nan,
                },
                {
                    "mode": mode,
                    "metric": "queries_with_positive_cross_batch",
                    "value": int((group["n_positive_batches"] > 1).sum()),
                },
                {
                    "mode": mode,
                    "metric": "queries_with_positive_cross_plate",
                    "value": int((group["n_positive_plates"] > 1).sum()),
                },
                {
                    "mode": mode,
                    "metric": "queries_with_positive_cross_well",
                    "value": int((group["n_positive_wells"] > 1).sum()),
                },
            ]
        )
        for k in top_k:
            rows.extend(
                [
                    {
                        "mode": mode,
                        "metric": f"mean_hit_at_{k}",
                        "value": float(evaluable[f"hit_at_{k}"].mean())
                        if len(evaluable)
                        else np.nan,
                    },
                    {
                        "mode": mode,
                        "metric": f"mean_recall_at_{k}",
                        "value": float(evaluable[f"recall_at_{k}"].mean())
                        if len(evaluable)
                        else np.nan,
                    },
                ]
            )
    return pd.DataFrame(rows)


def summarize_multiseed_text_profile_retrieval(
    by_seed_summary: pd.DataFrame,
    *,
    bootstrap_samples: int = 1000,
    ci: float = 0.95,
) -> pd.DataFrame:
    """Aggregate per-seed baseline metrics with simple bootstrap confidence intervals."""

    required = {"seed", "mode", "metric", "value"}
    missing = sorted(required.difference(by_seed_summary.columns))
    if missing:
        raise ValueError(f"Multi-seed summary is missing required columns: {missing}")
    rows: list[dict[str, object]] = []
    rng = np.random.default_rng(0)
    alpha = (1 - ci) / 2
    for (mode, metric), group in by_seed_summary.groupby(["mode", "metric"], sort=False):
        values = group["value"].to_numpy(dtype=float)
        finite = values[np.isfinite(values)]
        if len(finite):
            boot_means = np.array(
                [
                    float(np.mean(rng.choice(finite, size=len(finite), replace=True)))
                    for _ in range(max(bootstrap_samples, 1))
                ]
            )
            ci_low, ci_high = np.quantile(boot_means, [alpha, 1 - alpha])
            row = {
                "mode": mode,
                "metric": metric,
                "seed_count": int(len(group)),
                "finite_seed_count": int(len(finite)),
                "mean": float(np.mean(finite)),
                "std": float(np.std(finite, ddof=1)) if len(finite) > 1 else 0.0,
                "min": float(np.min(finite)),
                "max": float(np.max(finite)),
                "median": float(np.median(finite)),
                "ci95_low": float(ci_low),
                "ci95_high": float(ci_high),
            }
        else:
            row = {
                "mode": mode,
                "metric": metric,
                "seed_count": int(len(group)),
                "finite_seed_count": 0,
                "mean": np.nan,
                "std": np.nan,
                "min": np.nan,
                "max": np.nan,
                "median": np.nan,
                "ci95_low": np.nan,
                "ci95_high": np.nan,
            }
        rows.append(row)
    return pd.DataFrame(rows)


def _with_enrichment_over_random(summary: pd.DataFrame) -> pd.DataFrame:
    rows = [summary]
    random_map = (
        summary[summary["mode"] == "random"].set_index("metric")["value"].astype(float).to_dict()
    )
    enrichment_rows: list[dict[str, object]] = []
    for _, row in summary.iterrows():
        metric = str(row["metric"])
        if metric not in random_map:
            continue
        random_value = float(random_map[metric])
        mode_value = float(row["value"])
        if metric.startswith("n_") or not np.isfinite(random_value) or random_value <= 0:
            continue
        enrichment_rows.append(
            {
                "mode": row["mode"],
                "metric": f"enrichment_over_random::{metric}",
                "value": mode_value / random_value if np.isfinite(mode_value) else np.nan,
                "seed": row.get("seed"),
            }
        )
    if enrichment_rows:
        rows.append(pd.DataFrame(enrichment_rows))
    return pd.concat(rows, ignore_index=True)


def _score_queries(
    queries: pd.DataFrame,
    profiles: pd.DataFrame,
    scores: np.ndarray,
    labels: np.ndarray,
    *,
    scored_query_texts: list[str],
    top_k: list[int],
    mode: str,
    schema: dict[str, Any],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    per_query_rows: list[dict[str, object]] = []
    hit_rows: list[dict[str, object]] = []
    max_k = max(top_k)
    batch_column = schema["likely_batch_column"]
    plate_column = schema["likely_plate_column"]
    well_column = schema["likely_well_column"]

    for query_index, query in queries.reset_index(drop=True).iterrows():
        target_label = _clean_label(query["target_label"])
        positives = labels == target_label
        order = np.argsort(scores[query_index])[::-1]
        y_true = positives.astype(int)
        average_precision = (
            float(average_precision_score(y_true, scores[query_index]))
            if positives.any()
            else np.nan
        )
        row = {
            "mode": mode,
            "query_id": query["query_id"],
            "query_text": query["query_text"],
            "scored_query_text": scored_query_texts[query_index],
            "target_label": target_label,
            "label_column": query["label_column"],
            "n_positives": int(positives.sum()),
            "average_precision": average_precision,
            "n_positive_batches": _n_unique_positive_values(profiles, positives, batch_column),
            "n_positive_plates": _n_unique_positive_values(profiles, positives, plate_column),
            "n_positive_wells": _n_unique_positive_values(profiles, positives, well_column),
        }
        for k in top_k:
            top = order[:k]
            top_positive_count = int(positives[top].sum())
            row[f"hit_at_{k}"] = float(top_positive_count > 0)
            row[f"recall_at_{k}"] = (
                float(top_positive_count / positives.sum()) if positives.sum() else np.nan
            )
        per_query_rows.append(row)
        for rank, profile_index in enumerate(order[:max_k], start=1):
            profile = profiles.iloc[profile_index]
            hit_rows.append(
                {
                    "mode": mode,
                    "query_id": query["query_id"],
                    "scored_query_text": scored_query_texts[query_index],
                    "rank": rank,
                    "profile_id": profile["profile_id"],
                    "candidate_label": labels[profile_index],
                    "is_positive": bool(positives[profile_index]),
                    "score": float(scores[query_index, profile_index]),
                    "batch": _profile_value(profile, batch_column),
                    "plate": _profile_value(profile, plate_column),
                    "well": _profile_value(profile, well_column),
                }
            )
    return per_query_rows, hit_rows


def _tfidf_scores(query_texts: list[str], candidate_texts: list[str]) -> np.ndarray:
    corpus = [*query_texts, *candidate_texts]
    try:
        matrix = TfidfVectorizer(lowercase=True, ngram_range=(1, 2)).fit_transform(corpus)
    except ValueError:
        return np.zeros((len(query_texts), len(candidate_texts)), dtype=float)
    query_matrix = matrix[: len(query_texts)]
    profile_matrix = matrix[len(query_texts) :]
    return cosine_similarity(query_matrix, profile_matrix)


def _query_texts_for_identifier_stripped(queries: pd.DataFrame) -> list[str]:
    if "mechanism_query_text" not in queries.columns:
        return queries["query_text"].astype(str).tolist()
    texts = []
    for _, row in queries.iterrows():
        mechanism_text = _clean_label(row.get("mechanism_query_text", ""))
        texts.append(mechanism_text if _is_nonempty(mechanism_text) else str(row["query_text"]))
    return texts


def _metadata_text(row: pd.Series, columns: list[str]) -> str:
    values = [_clean_label(row.get(column, "")) for column in columns]
    return " ".join(value for value in values if _is_nonempty(value))


def _first_nonempty(row: pd.Series, columns: list[str]) -> str:
    for column in columns:
        value = _clean_label(row.get(column, ""))
        if _is_nonempty(value):
            return value
    return ""


def _validate_queries(queries: pd.DataFrame) -> None:
    required = {"query_id", "query_text", "target_label", "label_column"}
    missing = sorted(required.difference(queries.columns))
    if missing:
        raise ValueError(f"Query table is missing required columns: {missing}")


def _n_unique_positive_values(
    frame: pd.DataFrame,
    positives: np.ndarray,
    column: str | None,
) -> int:
    if not column or column not in frame.columns:
        return 0
    values = frame.loc[positives, column].map(_clean_label)
    values = values[_valid_label_mask(values)]
    return int(values.nunique())


def _profile_value(row: pd.Series, column: str | None) -> str:
    if not column:
        return ""
    return _clean_label(row.get(column, ""))


def _clean_label(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _is_nonempty(value: object) -> bool:
    text = _clean_label(value)
    return text.lower() not in NULL_LABELS


def _valid_label_mask(values: pd.Series | np.ndarray) -> np.ndarray:
    return np.array([_is_nonempty(value) for value in values], dtype=bool)
