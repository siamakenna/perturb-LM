from __future__ import annotations

from scripts.build_rxrx_manifests import build_manifests
from perturb_lm.queries.build_queries import build_queries
from perturb_lm.retrieval.search import run_retrieval


def test_random_shuffled_and_lexical_retrieval_modes_run(tmp_path) -> None:
    site_manifest, perturbations = build_manifests("rxrx19a", "tests/fixtures", tmp_path)
    queries = build_queries("rxrx19a", perturbations)

    for mode in ["random", "shuffled", "lexical"]:
        site_results, perturbation_results = run_retrieval(
            queries,
            site_manifest,
            dataset="rxrx19a",
            mode=mode,
            top_k=2,
            seed=3,
        )
        assert len(site_results) == len(queries) * 2
        assert {"query_id", "site_id", "perturbation_key", "score"}.issubset(site_results.columns)
        assert perturbation_results["rank"].min() == 1


def test_lexical_retrieval_promotes_matching_perturbation(tmp_path) -> None:
    site_manifest, perturbations = build_manifests("rxrx19a", "tests/fixtures", tmp_path)
    queries = build_queries("rxrx19a", perturbations)
    remdesivir_query = queries[queries["query_text"].str.contains("Remdesivir")].head(1)

    _, perturbation_results = run_retrieval(
        remdesivir_query,
        site_manifest,
        dataset="rxrx19a",
        mode="lexical",
        top_k=2,
    )

    assert "Remdesivir" in perturbation_results.iloc[0]["perturbation_key"]
