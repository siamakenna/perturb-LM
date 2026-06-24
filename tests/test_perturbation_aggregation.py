from __future__ import annotations

import pandas as pd

from perturb_lm.retrieval.aggregate import aggregate_site_results


def _results() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "query_id": "q1",
                "dataset": "rxrx1",
                "rank": 1,
                "site_id": "s1",
                "perturbation_key": "p1",
                "perturbation_id": "id1",
                "score": 0.8,
                "experiment": "e1",
                "plate": "pl1",
                "well": "A01",
                "site": "1",
                "cell_type": "HUVEC",
                "condition_label": "control",
            },
            {
                "query_id": "q1",
                "dataset": "rxrx1",
                "rank": 2,
                "site_id": "s2",
                "perturbation_key": "p1",
                "perturbation_id": "id1",
                "score": 0.5,
                "experiment": "e1",
                "plate": "pl1",
                "well": "A01",
                "site": "2",
                "cell_type": "HUVEC",
                "condition_label": "control",
            },
            {
                "query_id": "q1",
                "dataset": "rxrx1",
                "rank": 3,
                "site_id": "s3",
                "perturbation_key": "p2",
                "perturbation_id": "id2",
                "score": 0.7,
                "experiment": "e2",
                "plate": "pl2",
                "well": "B01",
                "site": "1",
                "cell_type": "HUVEC",
                "condition_label": "control",
            },
        ]
    )


def test_max_aggregation_preserves_rank_ordering() -> None:
    aggregated = aggregate_site_results(_results(), method="max")

    assert list(aggregated["perturbation_key"]) == ["p1", "p2"]
    assert list(aggregated["rank"]) == [1, 2]
    assert aggregated.iloc[0]["score"] == 0.8


def test_mean_and_reciprocal_rank_aggregation() -> None:
    mean = aggregate_site_results(_results(), method="mean")
    reciprocal = aggregate_site_results(_results(), method="reciprocal_rank")

    assert mean.loc[mean["perturbation_key"] == "p1", "score"].iloc[0] == 0.65
    assert reciprocal.loc[reciprocal["perturbation_key"] == "p1", "score"].iloc[0] == 1.5
