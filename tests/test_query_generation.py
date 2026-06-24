from __future__ import annotations

from scripts.build_rxrx_manifests import build_manifests
from perturb_lm.queries.build_queries import build_queries


def test_rxrx1_query_generation_from_manifest(tmp_path) -> None:
    _, perturbations = build_manifests("rxrx1", data_root="tests/fixtures", out_dir=tmp_path)
    queries = build_queries("rxrx1", perturbations)

    assert len(queries) == len(perturbations) * 3
    assert queries["query_text"].str.contains("siRNA perturbation").any()
    assert queries["positive_perturbation_keys"].notna().all()
    assert queries["positive_perturbation_ids"].notna().all()


def test_rxrx19a_query_generation_from_manifest(tmp_path) -> None:
    _, perturbations = build_manifests("rxrx19a", data_root="tests/fixtures", out_dir=tmp_path)
    queries = build_queries("rxrx19a", perturbations)

    assert len(queries) == len(perturbations) * 4
    assert queries["query_text"].str.contains("SARS-CoV-2 infected").any()
