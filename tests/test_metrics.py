from __future__ import annotations

import pandas as pd

from perturb_lm.retrieval.baselines import random_retrieval_baseline
from perturb_lm.retrieval.metrics import (
    average_precision,
    enrichment_over_random,
    hit_at_k,
    mean_average_precision,
    recall_at_k,
    same_batch_at_k,
    same_cell_type_at_k,
    same_plate_at_k,
)


def _queries() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "query_id": "q1",
                "dataset": "rxrx1",
                "positive_perturbation_keys": "p1",
                "positive_perturbation_ids": "id1",
            },
            {
                "query_id": "q2",
                "dataset": "rxrx1",
                "positive_perturbation_keys": "p2",
                "positive_perturbation_ids": "id2",
            },
        ]
    )


def _results() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"query_id": "q1", "dataset": "rxrx1", "rank": 1, "perturbation_key": "p1", "score": 0.9, "experiment": "e1", "plate": "pl1", "cell_type": "A"},
            {"query_id": "q1", "dataset": "rxrx1", "rank": 2, "perturbation_key": "p2", "score": 0.2, "experiment": "e1", "plate": "pl2", "cell_type": "B"},
            {"query_id": "q2", "dataset": "rxrx1", "rank": 1, "perturbation_key": "p1", "score": 0.8, "experiment": "e2", "plate": "pl3", "cell_type": "A"},
            {"query_id": "q2", "dataset": "rxrx1", "rank": 2, "perturbation_key": "p2", "score": 0.7, "experiment": "e2", "plate": "pl3", "cell_type": "A"},
        ]
    )


def test_core_metrics() -> None:
    queries = _queries()
    results = _results()

    assert hit_at_k(results, queries, 1) == 0.5
    assert recall_at_k(results, queries, 1) == 0.5
    assert average_precision(results[results["query_id"] == "q2"], {"p2"}) == 0.5
    assert mean_average_precision(results, queries) == 0.75
    assert enrichment_over_random(0.5, 0.25) == 2.0


def test_same_metadata_metrics() -> None:
    results = _results()

    assert same_batch_at_k(results, 2) == 1.0
    assert same_plate_at_k(results, 2) == 0.75
    assert same_cell_type_at_k(results, 2) == 0.75


def test_random_baseline_is_deterministic() -> None:
    queries = _queries()
    candidates = pd.DataFrame(
        [
            {"perturbation_key": "p1", "perturbation_id": "id1"},
            {"perturbation_key": "p2", "perturbation_id": "id2"},
        ]
    )

    first = random_retrieval_baseline(queries, candidates, seed=7, top_k=2)
    second = random_retrieval_baseline(queries, candidates, seed=7, top_k=2)

    pd.testing.assert_frame_equal(first, second)
