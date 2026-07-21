"""Metadata-derived text-to-profile retrieval baselines for JUMP profiles."""

from __future__ import annotations

import hashlib
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
    "Metadata_negcon_control_type",
]
PROHIBITED_IDENTIFIER_TEXT_COLUMN_CANDIDATES = [
    "Metadata_broad_sample",
    "Metadata_pert_iname",
    "Metadata_InChIKey",
    "Metadata_smiles",
    "Metadata_target_sequence",
    "Metadata_Plate",
    "Metadata_Well",
    "Metadata_Batch",
    "profile_id",
    "source_profile_file",
    "source_profile_row",
]
QUERY_SELECTION_MODES = {"all", "random", "stratified"}
BOOTSTRAP_METRICS = [
    "average_precision",
    "hit_at_1",
    "hit_at_5",
    "hit_at_10",
    "recall_at_1",
    "recall_at_5",
    "recall_at_10",
]


def build_metadata_text_queries(
    profiles: pd.DataFrame,
    *,
    label_column: str,
    query_limit: int | None = None,
    query_selection_mode: str = "all",
    seed: int = 0,
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
        control_type = _first_nonempty(
            row,
            ["Metadata_control_type", "Metadata_negcon_control_type"],
        )
        is_control = bool(
            "control" in control_type.lower()
            or "control" in pert_type.lower()
            or "negcon" in control_type.lower()
            or "negcon" in pert_type.lower()
        )
        plate_coverage = _group_nunique(group, ["Metadata_Plate", "Metadata_plate", "plate"])
        replicate_count = int(len(group))
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
                "perturbation_type_stratum": pert_type,
                "control_status_stratum": "control" if is_control else "non_control",
                "replicate_count_bin": _count_bin(replicate_count),
                "plate_coverage_bin": _count_bin(plate_coverage),
                "treatment_label_available": bool(_is_nonempty(label)),
            }
        )
    queries = pd.DataFrame(rows)
    selected, _ = select_text_profile_queries(
        queries,
        query_limit=query_limit,
        mode=query_selection_mode,
        seed=seed,
    )
    return selected


def run_text_profile_retrieval(
    data_root: Path | str = Path("data/raw/jump_pilot"),
    *,
    queries: pd.DataFrame | None = None,
    label_column: str | None = None,
    profile_files: list[Path | str] | None = None,
    max_rows: int | None = None,
    query_limit: int | None = None,
    query_selection_mode: str | None = None,
    top_k: list[int] | None = None,
    seed: int = 0,
    include_hits: bool = True,
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
    prohibited_identifier_text_columns = [
        column
        for column in PROHIBITED_IDENTIFIER_TEXT_COLUMN_CANDIDATES
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
            query_limit=None,
            query_selection_mode="all",
            seed=seed,
        )
    else:
        queries = queries.copy()
    _validate_queries(queries)
    selection_mode = query_selection_mode or ("stratified" if query_limit is not None else "all")
    queries, selection_report = select_text_profile_queries(
        queries,
        query_limit=query_limit,
        mode=selection_mode,
        seed=seed,
    )

    if indexed_profiles.empty or queries.empty:
        raise ValueError("Text-to-profile retrieval requires non-empty profiles and queries.")

    query_texts = queries["query_text"].astype(str).tolist()
    mechanism_query_texts = _query_texts_for_identifier_stripped(queries)
    prohibited_values = _prohibited_identifier_values(
        indexed_profiles,
        prohibited_identifier_text_columns,
    )
    _validate_no_identifier_leakage(
        mechanism_query_texts,
        prohibited_values=prohibited_values,
        context="identifier-stripped query text",
    )
    scores = _tfidf_scores(
        query_texts,
        indexed_profiles["_candidate_text"].astype(str).tolist(),
    )
    identifier_candidate_texts = indexed_profiles[
        "_identifier_stripped_candidate_text"
    ].astype(str).tolist()
    _validate_no_identifier_leakage(
        identifier_candidate_texts,
        prohibited_values=prohibited_values,
        context="identifier-stripped candidate text",
    )
    identifier_stripped_scores = _tfidf_scores(
        mechanism_query_texts,
        identifier_candidate_texts,
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
            include_hits=include_hits,
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
        "query_selection": selection_report,
        "label_column": label_column,
        "text_columns": text_columns,
        "identifier_stripped_text_columns": identifier_stripped_text_columns,
        "prohibited_identifier_text_columns": prohibited_identifier_text_columns,
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
                "and excludes target sequences; it should be interpreted as the tougher "
                "lexical control."
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
    query_selection_mode: str | None = None,
    top_k: list[int] | None = None,
    seeds: list[int] | None = None,
    bootstrap_samples: int = 1000,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Run metadata controls across deterministic seeds and summarize stability."""

    seeds = seeds or [0, 1, 2, 3, 4]
    if len(seeds) < 3:
        raise ValueError("At least three seeds are required for multi-seed baselines.")
    if len(set(seeds)) != len(seeds) or any(seed < 0 for seed in seeds):
        raise ValueError("Seeds must be unique non-negative integers.")

    all_summary_rows: list[pd.DataFrame] = []
    all_per_query_rows: list[pd.DataFrame] = []
    metadata: dict[str, Any] | None = None
    for seed in seeds:
        per_query, _, summary, run_metadata = run_text_profile_retrieval(
            data_root,
            queries=queries,
            label_column=label_column,
            profile_files=profile_files,
            max_rows=max_rows,
            query_limit=query_limit,
            query_selection_mode=query_selection_mode,
            top_k=top_k,
            seed=seed,
            include_hits=False,
        )
        seed_per_query = per_query.copy()
        seed_per_query["seed"] = seed
        all_per_query_rows.append(seed_per_query)
        seed_summary = summary.copy()
        seed_summary["seed"] = seed
        all_summary_rows.append(_with_enrichment_over_random(seed_summary))
        metadata = run_metadata

    by_seed = pd.concat(all_summary_rows, ignore_index=True)
    per_query_by_seed = pd.concat(all_per_query_rows, ignore_index=True)
    aggregate = summarize_multiseed_text_profile_retrieval(
        by_seed,
        bootstrap_samples=bootstrap_samples,
    )
    bootstrap = summarize_query_bootstrap(
        per_query_by_seed,
        top_k=top_k or [1, 5, 10],
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
    return by_seed, aggregate, bootstrap, result_metadata


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


def summarize_query_bootstrap(
    per_query_by_seed: pd.DataFrame,
    *,
    top_k: list[int],
    bootstrap_samples: int = 1000,
    seed: int = 0,
    reference_modes: list[str] | None = None,
) -> pd.DataFrame:
    """Build paired query-bootstrap CIs from retained per-query metrics."""

    reference_modes = reference_modes or ["identifier_stripped_tfidf", "random"]
    required = {"seed", "mode", "query_id", "n_positives"}
    missing = sorted(required.difference(per_query_by_seed.columns))
    if missing:
        raise ValueError(f"Per-query bootstrap input is missing columns: {missing}")
    metric_columns = [
        metric
        for metric in [
            "average_precision",
            *[f"hit_at_{k}" for k in top_k],
            *[f"recall_at_{k}" for k in top_k],
        ]
        if metric in per_query_by_seed.columns
    ]
    rng = np.random.default_rng(seed)
    rows: list[dict[str, object]] = []
    for mode, group in per_query_by_seed.groupby("mode", sort=False):
        deterministic = mode in {"metadata_tfidf", "identifier_stripped_tfidf"}
        mode_group = group[group["seed"] == group["seed"].min()] if deterministic else group
        rows.extend(
            _bootstrap_mode_rows(
                mode_group,
                mode=mode,
                metric_columns=metric_columns,
                rng=rng,
                bootstrap_samples=bootstrap_samples,
                deterministic=deterministic,
            )
        )
    for reference_mode in reference_modes:
        if reference_mode not in set(per_query_by_seed["mode"]):
            continue
        rows.extend(
            _paired_difference_rows(
                per_query_by_seed,
                reference_mode=reference_mode,
                metric_columns=metric_columns,
                rng=rng,
                bootstrap_samples=bootstrap_samples,
            )
        )
    return pd.DataFrame(rows)


def select_text_profile_queries(
    queries: pd.DataFrame,
    *,
    query_limit: int | None,
    mode: str,
    seed: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Select queries deterministically without order-biased head sampling."""

    if mode not in QUERY_SELECTION_MODES:
        raise ValueError(f"Unsupported query selection mode: {mode}")
    work = queries.copy()
    if query_limit is None or mode == "all":
        selected = work.sort_values("query_id", kind="mergesort").reset_index(drop=True)
        return selected, _selection_report(selected, mode="all", seed=seed)
    if query_limit <= 0:
        raise ValueError("query_limit must be positive when provided.")
    if len(work) <= query_limit:
        selected = work.sort_values("query_id", kind="mergesort").reset_index(drop=True)
        return selected, _selection_report(selected, mode=mode, seed=seed)
    if mode == "random":
        selected = (
            work.assign(_sample_key=work["query_id"].map(lambda value: _stable_score(value, seed)))
            .sort_values(["_sample_key", "query_id"], kind="mergesort")
            .head(query_limit)
            .drop(columns=["_sample_key"])
            .sort_values("query_id", kind="mergesort")
            .reset_index(drop=True)
        )
        return selected, _selection_report(selected, mode=mode, seed=seed)
    stratum_columns = [
        "perturbation_type_stratum",
        "control_status_stratum",
        "replicate_count_bin",
        "plate_coverage_bin",
        "treatment_label_available",
    ]
    missing = sorted(set(stratum_columns).difference(work.columns))
    if missing:
        raise ValueError(f"Stratified query selection is missing strata columns: {missing}")
    work["_stratum"] = work[stratum_columns].astype(str).agg("|".join, axis=1)
    selected_parts: list[pd.DataFrame] = []
    stratum_sizes = work["_stratum"].value_counts(sort=False).sort_index()
    if len(stratum_sizes) > query_limit:
        raise ValueError(
            "Stratified query selection requires query_limit to be at least the "
            f"number of available strata ({len(stratum_sizes)})."
        )
    raw_allocations = stratum_sizes / len(work) * query_limit
    allocations = np.floor(raw_allocations).astype(int)
    allocations[allocations == 0] = 1
    while int(allocations.sum()) > query_limit:
        reducible = allocations[allocations > 1]
        if reducible.empty:
            break
        allocations.loc[reducible.index[-1]] -= 1
    remainder = query_limit - int(allocations.sum())
    if remainder > 0:
        fractions = (raw_allocations - np.floor(raw_allocations)).sort_values(ascending=False)
        for stratum in fractions.index[:remainder]:
            allocations.loc[stratum] += 1
    for stratum, group in work.groupby("_stratum", sort=True):
        take = int(min(allocations.get(stratum, 0), len(group)))
        sample_keys = group["query_id"].map(lambda value: _stable_score(value, seed))
        part = (
            group.assign(_sample_key=sample_keys)
            .sort_values(["_sample_key", "query_id"], kind="mergesort")
            .head(take)
        )
        selected_parts.append(part)
    selected_with_strata = (
        pd.concat(selected_parts, ignore_index=True)
        .drop(columns=["_sample_key"])
        .sort_values("query_id", kind="mergesort")
        .reset_index(drop=True)
    )
    report = _selection_report(
        selected_with_strata,
        mode=mode,
        seed=seed,
        stratum_column="_stratum",
    )
    selected = selected_with_strata.drop(columns=["_stratum"])
    return selected, report


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
    include_hits: bool = True,
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
        if include_hits:
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


def _selection_report(
    selected: pd.DataFrame,
    *,
    mode: str,
    seed: int,
    stratum_column: str | None = None,
) -> dict[str, Any]:
    query_ids = selected["query_id"].astype(str).sort_values().tolist()
    report = {
        "method": mode,
        "seed": seed,
        "n_selected_queries": int(len(selected)),
        "selection_checksum": hashlib.sha256("\n".join(query_ids).encode("utf-8")).hexdigest(),
    }
    if stratum_column and stratum_column in selected.columns:
        counts = selected[stratum_column].astype(str).value_counts().sort_index()
        report["stratum_counts"] = {
            f"stratum_{index:03d}": int(value)
            for index, value in enumerate(counts.to_list(), start=1)
        }
        report["stratum_count"] = int(len(counts))
    return report


def _stable_score(value: object, seed: int) -> str:
    return hashlib.sha256(f"{seed}|{value}".encode()).hexdigest()


def _count_bin(count: int) -> str:
    if count <= 1:
        return "1"
    if count <= 3:
        return "2-3"
    if count <= 10:
        return "4-10"
    return "11+"


def _group_nunique(group: pd.DataFrame, columns: list[str]) -> int:
    for column in columns:
        if column in group.columns:
            return int(group[column].map(_clean_label).replace("", np.nan).nunique(dropna=True))
    return 0


def _prohibited_identifier_values(frame: pd.DataFrame, columns: list[str]) -> set[str]:
    values: set[str] = set()
    for column in columns:
        if column not in frame.columns:
            continue
        for value in frame[column].dropna().astype(str):
            clean = value.strip().lower()
            if clean and clean not in NULL_LABELS and len(clean) >= 4:
                values.add(clean)
    return values


def _validate_no_identifier_leakage(
    texts: list[str],
    *,
    prohibited_values: set[str],
    context: str,
) -> None:
    for text in texts:
        lowered = str(text).lower()
        if any(value and value in lowered for value in prohibited_values):
            raise ValueError(f"Prohibited identifier value appeared in {context}.")


def _bootstrap_mode_rows(
    group: pd.DataFrame,
    *,
    mode: str,
    metric_columns: list[str],
    rng: np.random.Generator,
    bootstrap_samples: int,
    deterministic: bool,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for seed_value, seed_group in group.groupby("seed", sort=True):
        evaluable = seed_group[seed_group["n_positives"] > 0]
        n_queries = int(len(seed_group))
        n_evaluable_queries = int(len(evaluable))
        for metric in metric_columns:
            values = (
                evaluable[metric].to_numpy(dtype=float)
                if metric in evaluable
                else np.array([])
            )
            finite = values[np.isfinite(values)]
            rows.append(
                _bootstrap_estimate_row(
                    mode=mode,
                    metric=metric,
                    values=finite,
                    n_queries=n_queries,
                    n_evaluable_queries=n_evaluable_queries,
                    rng=rng,
                    bootstrap_samples=bootstrap_samples,
                    seed_value=int(seed_value),
                    deterministic=deterministic,
                )
            )
        if deterministic:
            break
    return rows


def _bootstrap_estimate_row(
    *,
    mode: str,
    metric: str,
    values: np.ndarray,
    n_queries: int,
    n_evaluable_queries: int,
    rng: np.random.Generator,
    bootstrap_samples: int,
    seed_value: int,
    deterministic: bool,
) -> dict[str, object]:
    if len(values):
        boot = np.array(
            [
                float(np.mean(rng.choice(values, size=len(values), replace=True)))
                for _ in range(max(bootstrap_samples, 1))
            ]
        )
        ci_low, ci_high = np.quantile(boot, [0.025, 0.975])
        point = float(np.mean(values))
    else:
        ci_low = ci_high = point = np.nan
    return {
        "mode": mode,
        "comparison": "point_estimate",
        "metric": metric,
        "seed": seed_value,
        "deterministic_mode": deterministic,
        "n_queries": n_queries,
        "n_evaluable_queries": n_evaluable_queries,
        "estimate": point,
        "ci95_low": float(ci_low) if np.isfinite(ci_low) else np.nan,
        "ci95_high": float(ci_high) if np.isfinite(ci_high) else np.nan,
    }


def _paired_difference_rows(
    per_query: pd.DataFrame,
    *,
    reference_mode: str,
    metric_columns: list[str],
    rng: np.random.Generator,
    bootstrap_samples: int,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    reference = per_query[per_query["mode"] == reference_mode]
    for mode in sorted(set(per_query["mode"])):
        if mode == reference_mode:
            continue
        mode_frame = per_query[per_query["mode"] == mode]
        for seed_value in sorted(set(mode_frame["seed"])):
            mode_seed = mode_frame[mode_frame["seed"] == seed_value]
            reference_seed_value = (
                reference["seed"].min()
                if reference_mode in {"metadata_tfidf", "identifier_stripped_tfidf"}
                else seed_value
            )
            ref_seed = reference[reference["seed"] == reference_seed_value]
            merged = mode_seed.merge(
                ref_seed,
                on="query_id",
                suffixes=("", "_reference"),
                how="inner",
            )
            for metric in metric_columns:
                if metric not in merged or f"{metric}_reference" not in merged:
                    continue
                evaluable = merged[
                    (merged["n_positives"] > 0) & (merged["n_positives_reference"] > 0)
                ]
                n_queries = int(len(merged))
                n_evaluable_queries = int(len(evaluable))
                diff = (
                    evaluable[metric].to_numpy(dtype=float)
                    - evaluable[f"{metric}_reference"].to_numpy(dtype=float)
                )
                finite = diff[np.isfinite(diff)]
                rows.append(
                    _paired_difference_row(
                        mode=mode,
                        reference_mode=reference_mode,
                        metric=metric,
                        values=finite,
                        n_queries=n_queries,
                        n_evaluable_queries=n_evaluable_queries,
                        rng=rng,
                        bootstrap_samples=bootstrap_samples,
                        seed_value=int(seed_value),
                    )
                )
            if mode in {"metadata_tfidf", "identifier_stripped_tfidf"}:
                break
    return rows


def _paired_difference_row(
    *,
    mode: str,
    reference_mode: str,
    metric: str,
    values: np.ndarray,
    n_queries: int,
    n_evaluable_queries: int,
    rng: np.random.Generator,
    bootstrap_samples: int,
    seed_value: int,
) -> dict[str, object]:
    if len(values):
        boot = np.array(
            [
                float(np.mean(rng.choice(values, size=len(values), replace=True)))
                for _ in range(max(bootstrap_samples, 1))
            ]
        )
        ci_low, ci_high = np.quantile(boot, [0.025, 0.975])
        point = float(np.mean(values))
    else:
        ci_low = ci_high = point = np.nan
    return {
        "mode": mode,
        "comparison": f"paired_difference_vs_{reference_mode}",
        "metric": metric,
        "seed": seed_value,
        "n_queries": n_queries,
        "n_evaluable_queries": n_evaluable_queries,
        "estimate": point,
        "ci95_low": float(ci_low) if np.isfinite(ci_low) else np.nan,
        "ci95_high": float(ci_high) if np.isfinite(ci_high) else np.nan,
    }


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
