from __future__ import annotations

import numpy as np
import pandas as pd

from perturb_lm.retrieval.text_embeddings import embed_query_text


def test_hashing_text_embeddings_are_deterministic() -> None:
    queries = pd.DataFrame({"query_text": ["viral cells treated with drug", "siRNA knockdown"]})

    first = embed_query_text(queries, mode="hashing", n_features=16)
    second = embed_query_text(queries, mode="hashing", n_features=16)

    assert first.shape == (2, 16)
    np.testing.assert_allclose(first, second)


def test_tfidf_text_embeddings_work_offline() -> None:
    queries = pd.DataFrame({"query_text": ["alpha beta", "beta gamma"]})

    embeddings = embed_query_text(queries, mode="tfidf", n_features=8)

    assert embeddings.shape[0] == 2
    assert embeddings.shape[1] <= 8
