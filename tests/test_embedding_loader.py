from __future__ import annotations

import numpy as np

from scripts.build_rxrx_manifests import build_manifests
from perturb_lm.retrieval.embeddings import load_site_embeddings


def test_embedding_loader_aligns_csv_to_manifest(tmp_path) -> None:
    site_manifest, _ = build_manifests("rxrx1", "tests/fixtures", tmp_path)

    result = load_site_embeddings("tests/fixtures/rxrx1_embeddings.csv", site_manifest)

    assert result.n_embeddings == 3
    assert result.dimension == 3
    assert result.matched == 3
    assert result.unmatched == 1
    np.testing.assert_allclose(np.linalg.norm(result.embeddings, axis=1), 1.0)
