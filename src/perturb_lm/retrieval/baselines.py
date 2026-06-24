"""Deterministic retrieval baselines."""

from __future__ import annotations

import numpy as np
import pandas as pd


def random_retrieval_baseline(
    queries: pd.DataFrame,
    candidates: pd.DataFrame,
    *,
    seed: int = 0,
    top_k: int | None = None,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    top_k = top_k or len(candidates)
    for _, query in queries.iterrows():
        shuffled = candidates.sample(frac=1.0, random_state=int(rng.integers(0, 2**31 - 1))).head(top_k)
        for rank, (_, candidate) in enumerate(shuffled.iterrows(), start=1):
            rows.append(_baseline_row(query, candidate, rank, score=1.0 / rank))
    return pd.DataFrame(rows)


def shuffled_label_baseline(
    queries: pd.DataFrame,
    candidates: pd.DataFrame,
    *,
    seed: int = 0,
    top_k: int | None = None,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    shuffled = candidates.copy().reset_index(drop=True)
    shuffled["perturbation_key"] = rng.permutation(shuffled["perturbation_key"].astype(str).to_numpy())
    shuffled["perturbation_id"] = rng.permutation(shuffled["perturbation_id"].astype(str).to_numpy())
    return random_retrieval_baseline(queries, shuffled, seed=seed, top_k=top_k)


def _baseline_row(query: pd.Series, candidate: pd.Series, rank: int, score: float) -> dict[str, object]:
    return {
        "query_id": query["query_id"],
        "dataset": query["dataset"],
        "rank": rank,
        "site_id": candidate.get("site_id", ""),
        "perturbation_key": candidate["perturbation_key"],
        "perturbation_id": candidate["perturbation_id"],
        "score": score,
        "experiment": candidate.get("experiment", ""),
        "plate": candidate.get("plate", ""),
        "well": candidate.get("well", ""),
        "site": candidate.get("site", ""),
        "cell_type": candidate.get("cell_type", ""),
        "condition_label": candidate.get("condition_label", ""),
    }
