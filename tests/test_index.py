from __future__ import annotations

from scripts.build_rxrx_manifests import build_manifests
from perturb_lm.retrieval.embeddings import load_site_embeddings
from perturb_lm.retrieval.index import load_index_matrix, save_sklearn_index


def test_save_and_load_sklearn_index_artifacts(tmp_path) -> None:
    site_manifest, _ = build_manifests("rxrx1", "tests/fixtures", tmp_path / "processed")
    result = load_site_embeddings("tests/fixtures/rxrx1_embeddings.csv", site_manifest)

    saved = save_sklearn_index(result, tmp_path / "index", dataset="rxrx1")
    embeddings, id_mapping, metadata = load_index_matrix(saved.out_dir)

    assert saved.index_path.exists()
    assert embeddings.shape == (3, 3)
    assert len(id_mapping) == 3
    assert metadata["backend"] == "sklearn-nearest-neighbors"
