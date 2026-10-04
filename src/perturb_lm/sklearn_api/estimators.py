"""Small offline estimators with sklearn parameter and cloning semantics."""

from __future__ import annotations

import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.cross_decomposition import CCA, PLSRegression
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler
from sklearn.utils.validation import check_array, check_is_fitted


class TfidfTextEmbedder(TransformerMixin, BaseEstimator):
    def __init__(self, analyzer: str = "word", ngram_range: tuple[int, int] = (1, 2)):
        self.analyzer = analyzer
        self.ngram_range = ngram_range

    def fit(self, X, y=None):
        self.vectorizer_ = TfidfVectorizer(analyzer=self.analyzer, ngram_range=self.ngram_range)
        self.vectorizer_.fit(X)
        return self

    def transform(self, X):
        check_is_fitted(self, "vectorizer_")
        return self.vectorizer_.transform(X)


class MorphologyEmbedder(TransformerMixin, BaseEstimator):
    """Precomputed numeric representations; train-only scaling, no image inference."""

    def __init__(self, standardize: bool = True):
        self.standardize = standardize

    def fit(self, X, y=None):
        X = check_array(X)
        self.n_features_in_ = X.shape[1]
        self.scaler_ = StandardScaler(with_mean=self.standardize, with_std=self.standardize).fit(X)
        return self

    def transform(self, X):
        check_is_fitted(self, "scaler_")
        X = check_array(X)
        if X.shape[1] != self.n_features_in_:
            raise ValueError("Morphology dimension differs from fitted representation")
        return self.scaler_.transform(X)


class AlignmentEstimator(TransformerMixin, BaseEstimator):
    """fit(text, morphology); transform(text) predicts morphology coordinates.

    PLS and CCA use their regression predict operation, not incompatible latent spaces.
    Unaligned cosine is only defined when both modalities already share dimensions.
    """

    def __init__(
        self,
        method: str = "ridge",
        alpha: float = 1.0,
        n_components: int = 2,
        random_state: int = 0,
        epochs: int = 100,
        hidden_dim: int = 32,
        learning_rate: float = 0.01,
        temperature: float = 0.1,
    ):
        self.method = method
        self.alpha = alpha
        self.n_components = n_components
        self.random_state = random_state
        self.epochs = epochs
        self.hidden_dim = hidden_dim
        self.learning_rate = learning_rate
        self.temperature = temperature

    def fit(self, X, y, *, group_ids=None, checkpoint=None):
        X = check_array(X, accept_sparse=True)
        y = check_array(y)
        if len(y) != X.shape[0]:
            raise ValueError("Alignment requires paired text and morphology rows")
        self.n_features_in_ = X.shape[1]
        self.n_outputs_ = y.shape[1]
        if len(y) < 2 or not np.any(np.std(y, axis=0) > 1e-12):
            raise ValueError("Degenerate morphology training targets")
        if self.method == "unaligned_cosine":
            if self.n_features_in_ != self.n_outputs_:
                raise ValueError(
                    "Unaligned cosine requires matching dimensions; no implicit projection"
                )
            self.model_ = None
        elif self.method == "ridge":
            self.model_ = Ridge(alpha=self.alpha, solver="lsqr").fit(X, y)
        elif self.method in {"pls", "cca"}:
            if not 1 <= self.n_components <= min(X.shape[0] - 1, X.shape[1], y.shape[1]):
                raise ValueError("n_components exceeds training matrix rank bounds")
            model = PLSRegression if self.method == "pls" else CCA
            self.model_ = model(n_components=self.n_components).fit(_dense(X), y)
        elif self.method in {"mlp_projection", "contrastive_projection"}:
            from perturb_lm.sklearn_api.neural import NeuralProjection

            self.model_ = NeuralProjection(
                "mse" if self.method == "mlp_projection" else "contrastive",
                self.hidden_dim,
                self.epochs,
                self.learning_rate,
                self.temperature,
                self.random_state,
            ).fit(_dense(X), y, group_ids=group_ids, checkpoint=checkpoint)
        else:
            raise NotImplementedError(
                f"{self.method} is planned; implement a reviewed Phase 2 backend"
            )
        self.state_metadata_ = {
            "method": self.method,
            "seed": self.random_state,
            "fit_scope": "train",
            "input_dimension": self.n_features_in_,
            "output_dimension": self.n_outputs_,
            "n_training_rows": len(y),
            "neural_state": getattr(self.model_, "state_metadata_", None),
        }
        return self

    def transform(self, X):
        check_is_fitted(self, "model_")
        X = check_array(X, accept_sparse=True)
        if X.shape[1] != self.n_features_in_:
            raise ValueError("Text dimension differs from fitted alignment")
        if self.model_ is None:
            return _dense(X)
        return self.model_.predict(_dense(X) if self.method != "ridge" else X)

    def predict(self, X):
        return self.transform(X)


def _dense(X):
    return X.toarray() if hasattr(X, "toarray") else np.asarray(X)


class RetrievalEstimator(BaseEstimator):
    """fit indexes the gallery; predict returns full score matrices, not class labels."""

    def __init__(self, method: str = "cosine", random_state: int = 0):
        self.method = method
        self.random_state = random_state

    def fit(self, X, y=None):
        if self.method not in {"cosine", "random", "shuffled_query", "exact_gene"}:
            raise ValueError("Unsupported retrieval method")
        self.gallery_ = (
            np.asarray(X, dtype=str)
            if self.method == "exact_gene"
            else check_array(X, accept_sparse=True).copy()
        )
        if self.method == "exact_gene" and self.gallery_.ndim != 1:
            raise ValueError("Exact-gene lookup expects one-dimensional gene symbols")
        return self

    def predict(self, X):
        check_is_fitted(self, "gallery_")
        if self.method == "exact_gene":
            query = np.asarray(X, dtype=str)
            if query.ndim != 1:
                raise ValueError("Exact-gene lookup expects one-dimensional gene symbols")
            valid = ~np.isin(query, ["", "nan", "None"])
            return ((query[:, None] == self.gallery_[None, :]) & valid[:, None]).astype(float)
        X = check_array(X, accept_sparse=True)
        rng = np.random.default_rng(self.random_state)
        if self.method == "random":
            return rng.random((X.shape[0], self.gallery_.shape[0]))
        if self.method == "shuffled_query":
            X = X[rng.permutation(X.shape[0])]
        return cosine_similarity(X, self.gallery_)
