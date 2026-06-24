"""Retrieval metrics for perturbation-level evaluation."""

from __future__ import annotations

import math
from collections.abc import Iterable

import pandas as pd


def _positive_set(value: object) -> set[str]:
    if isinstance(value, (list, tuple, set)):
        return {str(item) for item in value}
    if pd.isna(value):
        return set()
    return {part.strip() for part in str(value).split("|") if part.strip()}


def _query_positive_map(queries: pd.DataFrame, column: str = "positive_perturbation_keys") -> dict[str, set[str]]:
    return {str(row["query_id"]): _positive_set(row[column]) for _, row in queries.iterrows()}


def hit_at_k(results: pd.DataFrame, queries: pd.DataFrame, k: int) -> float:
    positives = _query_positive_map(queries)
    hits = []
    for query_id, group in results.sort_values("rank").groupby("query_id"):
        top = set(group.head(k)["perturbation_key"].astype(str))
        hits.append(float(bool(top & positives.get(str(query_id), set()))))
    return float(sum(hits) / len(hits)) if hits else 0.0


def recall_at_k(results: pd.DataFrame, queries: pd.DataFrame, k: int) -> float:
    positives = _query_positive_map(queries)
    recalls = []
    for query_id, group in results.sort_values("rank").groupby("query_id"):
        positive = positives.get(str(query_id), set())
        if not positive:
            continue
        top = set(group.head(k)["perturbation_key"].astype(str))
        recalls.append(len(top & positive) / len(positive))
    return float(sum(recalls) / len(recalls)) if recalls else 0.0


def average_precision(results_for_query: pd.DataFrame, positive_keys: Iterable[str]) -> float:
    positives = {str(key) for key in positive_keys}
    if not positives:
        return 0.0
    hits = 0
    precisions = []
    ranked = results_for_query.sort_values("rank")
    for rank, key in enumerate(ranked["perturbation_key"].astype(str), start=1):
        if key in positives:
            hits += 1
            precisions.append(hits / rank)
    return float(sum(precisions) / len(positives)) if precisions else 0.0


def mean_average_precision(results: pd.DataFrame, queries: pd.DataFrame) -> float:
    positives = _query_positive_map(queries)
    scores = []
    for query_id, group in results.groupby("query_id"):
        scores.append(average_precision(group, positives.get(str(query_id), set())))
    return float(sum(scores) / len(scores)) if scores else 0.0


def per_query_metrics(results: pd.DataFrame, queries: pd.DataFrame, top_k: list[int]) -> pd.DataFrame:
    positives = _query_positive_map(queries)
    rows = []
    for _, query in queries.iterrows():
        query_id = str(query["query_id"])
        group = results[results["query_id"].astype(str) == query_id].sort_values("rank")
        positive = positives.get(query_id, set())
        row: dict[str, object] = {
            "query_id": query_id,
            "dataset": query.get("dataset", ""),
            "n_positive_perturbations": len(positive),
            "average_precision": average_precision(group, positive),
        }
        for k in top_k:
            top = set(group.head(k)["perturbation_key"].astype(str))
            row[f"recall_at_{k}"] = len(top & positive) / len(positive) if positive else 0.0
            row[f"hit_at_{k}"] = float(bool(top & positive))
        rows.append(row)
    return pd.DataFrame(rows)


def evaluate_perturbation_retrieval(
    perturbation_results: pd.DataFrame,
    queries: pd.DataFrame,
    *,
    site_results: pd.DataFrame | None = None,
    top_k: list[int] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    top_k = top_k or [1, 5, 10]
    per_query = per_query_metrics(perturbation_results, queries, top_k)
    n_candidates = perturbation_results["perturbation_key"].nunique()
    avg_positives = float(per_query["n_positive_perturbations"].mean()) if len(per_query) else 0.0

    rows = [{"metric": "mAP", "value": float(per_query["average_precision"].mean()) if len(per_query) else 0.0}]
    for k in top_k:
        recall = float(per_query[f"recall_at_{k}"].mean()) if len(per_query) else 0.0
        hit = float(per_query[f"hit_at_{k}"].mean()) if len(per_query) else 0.0
        random_hit = random_hit_probability(n_candidates, avg_positives, k)
        rows.extend(
            [
                {"metric": f"Recall@{k}", "value": recall},
                {"metric": f"Hit@{k}", "value": hit},
                {"metric": f"EnrichmentOverRandom@{k}", "value": enrichment_over_random(hit, random_hit)},
            ]
        )
    if site_results is not None and len(site_results):
        rows.extend(
            [
                {"metric": "same-batch@10", "value": same_batch_at_k(site_results, 10)},
                {"metric": "same-plate@10", "value": same_plate_at_k(site_results, 10)},
                {"metric": "same-cell-type@10", "value": same_cell_type_at_k(site_results, 10)},
            ]
        )
    return pd.DataFrame(rows), per_query


def enrichment_over_random(observed: float, random_expected: float) -> float:
    if random_expected == 0:
        return math.inf if observed > 0 else 0.0
    return float(observed / random_expected)


def random_hit_probability(num_candidates: int, num_positives: float, k: int) -> float:
    if num_candidates <= 0 or num_positives <= 0 or k <= 0:
        return 0.0
    return float(min(1.0, (min(k, num_candidates) * num_positives) / num_candidates))


def same_batch_at_k(results: pd.DataFrame, k: int) -> float:
    return _same_value_at_k(results, "experiment", k)


def same_plate_at_k(results: pd.DataFrame, k: int) -> float:
    return _same_value_at_k(results, "plate", k)


def same_cell_type_at_k(results: pd.DataFrame, k: int) -> float:
    return _same_value_at_k(results, "cell_type", k)


def _same_value_at_k(results: pd.DataFrame, column: str, k: int) -> float:
    if column not in results.columns or "query_id" not in results.columns:
        raise ValueError(f"results must contain query_id and {column} columns")
    values = []
    for _, group in results.sort_values("rank").groupby("query_id"):
        query_value = group.iloc[0][column]
        top = group.head(k)
        values.append(float((top[column] == query_value).mean()))
    return float(sum(values) / len(values)) if values else 0.0
