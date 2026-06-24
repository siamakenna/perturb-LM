"""Aggregate site-level retrieval results to perturbation-level scores."""

from __future__ import annotations

import pandas as pd

from perturb_lm.schemas import validate_retrieval_results


def aggregate_site_results(results: pd.DataFrame, method: str = "max") -> pd.DataFrame:
    """Aggregate retrieval results by query and perturbation key."""

    validate_retrieval_results(results)
    method = method.lower()
    if method not in {"max", "mean", "reciprocal_rank"}:
        raise ValueError("method must be one of: max, mean, reciprocal_rank")

    work = results.copy()
    if method == "reciprocal_rank":
        work["_score"] = 1.0 / work["rank"].astype(float)
        agg = work.groupby(["query_id", "dataset", "perturbation_key", "perturbation_id"], as_index=False)[
            "_score"
        ].sum()
        agg = agg.rename(columns={"_score": "score"})
    else:
        agg_func = "max" if method == "max" else "mean"
        agg = work.groupby(["query_id", "dataset", "perturbation_key", "perturbation_id"], as_index=False)[
            "score"
        ].agg(agg_func)

    agg = agg.sort_values(["query_id", "score", "perturbation_key"], ascending=[True, False, True])
    agg["rank"] = agg.groupby("query_id").cumcount() + 1
    return agg[["query_id", "dataset", "rank", "perturbation_key", "perturbation_id", "score"]]
