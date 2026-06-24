"""Lightweight text embedding baselines."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import HashingVectorizer, TfidfVectorizer


def embed_query_text(
    queries: pd.DataFrame,
    *,
    mode: str = "hashing",
    text_column: str = "query_text",
    n_features: int = 256,
) -> np.ndarray:
    if text_column not in queries.columns:
        raise ValueError(f"queries is missing text column '{text_column}'.")
    texts = queries[text_column].fillna("").astype(str).tolist()
    mode = mode.lower()
    if mode in {"hashing", "offline"}:
        vectorizer = HashingVectorizer(n_features=n_features, alternate_sign=False, norm="l2")
        return vectorizer.transform(texts).toarray()
    if mode == "tfidf":
        vectorizer = TfidfVectorizer(max_features=n_features, norm="l2")
        return vectorizer.fit_transform(texts).toarray()
    if mode in {"sentence-transformer", "sentence_transformer"}:
        return _sentence_transformer_embeddings(texts)
    raise ValueError("Text embedding mode must be hashing, tfidf, or sentence-transformer.")


def _sentence_transformer_embeddings(texts: list[str]) -> np.ndarray:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "sentence-transformers is optional. Install it to use --text-embedding-mode sentence-transformer."
        ) from exc
    model = SentenceTransformer("all-MiniLM-L6-v2")
    return np.asarray(model.encode(texts, normalize_embeddings=True), dtype=float)
