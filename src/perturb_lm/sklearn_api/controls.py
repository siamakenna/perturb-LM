"""Offline lexical controls. BM25 is a ranker, not a dense embedding model."""

from __future__ import annotations

import re
from collections import Counter

import numpy as np
from sklearn.base import BaseEstimator
from sklearn.utils.validation import check_is_fitted


class BM25Retriever(BaseEstimator):
    """Robertson BM25 with positive log IDF and deterministic whitespace/word tokenization."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b

    def fit(self, X, y=None):
        if self.k1 <= 0 or not 0 <= self.b <= 1:
            raise ValueError("BM25 requires k1 > 0 and 0 <= b <= 1")
        documents = [Counter(re.findall(r"\w+", text.casefold())) for text in X]
        if not documents:
            raise ValueError("BM25 requires a nonempty candidate corpus")
        self.documents_ = documents
        self.lengths_ = np.array([sum(doc.values()) for doc in documents])
        self.average_length_ = max(float(self.lengths_.mean()), 1.0)
        frequency = Counter(token for doc in documents for token in doc)
        self.idf_ = {
            token: np.log1p((len(documents) - count + 0.5) / (count + 0.5))
            for token, count in frequency.items()
        }
        return self

    def predict(self, X):
        check_is_fitted(self, "documents_")
        queries = list(X)
        scores = np.zeros((len(queries), len(self.documents_)))
        denominator = self.k1 * (1 - self.b + self.b * self.lengths_ / self.average_length_)
        for i, text in enumerate(queries):
            for token in set(re.findall(r"\w+", text.casefold())):
                frequency = np.array([doc.get(token, 0) for doc in self.documents_])
                scores[i] += (
                    self.idf_.get(token, 0) * frequency * (self.k1 + 1) / (frequency + denominator)
                )
        return scores
