"""A paired-modality estimator with an explicit, independently indexed gallery."""

from __future__ import annotations

import pandas as pd
from sklearn.base import BaseEstimator, clone
from sklearn.utils.validation import check_is_fitted

from perturb_lm.sklearn_api.estimators import (
    AlignmentEstimator,
    MorphologyEmbedder,
    RetrievalEstimator,
    TfidfTextEmbedder,
)
from perturb_lm.sklearn_api.evaluation import MetricEvaluator
from perturb_lm.sklearn_api.queries import POLICIES, QueryPolicyTransformer
from perturb_lm.sklearn_api.splits import SplitSpec


class BenchmarkPipeline(BaseEstimator):
    """fit(X, y, gallery=..., gallery_y=...) pairs metadata with morphology rows.

    The gallery must belong to the held-out partition. predict returns full scores;
    evaluate adds exclusion accounting and score returns mAP. Adapters and planning
    remain outside the estimator; no I/O or optional model loading happens in fit.
    """

    def __init__(
        self,
        query_policy=None,
        text_embedder=None,
        morphology_embedder=None,
        alignment=None,
        retrieval=None,
        evaluator=None,
        split=None,
        synthetic: bool = False,
    ):
        self.query_policy = query_policy
        self.text_embedder = text_embedder
        self.morphology_embedder = morphology_embedder
        self.alignment = alignment
        self.retrieval = retrieval
        self.evaluator = evaluator
        self.split = split
        self.synthetic = synthetic

    def fit(self, X: pd.DataFrame, y, *, gallery: pd.DataFrame, gallery_y):
        self.split_ = self.split if self.split is not None else SplitSpec()
        self.split_.validate(X, gallery)
        if not X.split.eq("train").all() or not gallery.split.eq("test").all():
            raise ValueError("Pipeline requires explicit train and test membership")
        if len(X) != len(y) or len(gallery) != len(gallery_y):
            raise ValueError("Metadata and morphology must have identical paired row counts")
        self.query_policy_ = clone(
            self.query_policy if self.query_policy is not None else QueryPolicyTransformer()
        )
        policy = POLICIES[self.query_policy_.policy]
        if policy.provisional and not self.synthetic:
            raise ValueError(
                "Provisional query policies are synthetic-only pending scientific review"
            )
        self.query_policy_.fit(pd.concat([X, gallery], ignore_index=True))
        queries = self.query_policy_.transform(X)
        self.text_embedder_ = clone(
            self.text_embedder if self.text_embedder is not None else TfidfTextEmbedder()
        )
        text = self.text_embedder_.fit_transform(queries.rendered_text.tolist())
        self.morphology_embedder_ = clone(
            self.morphology_embedder
            if self.morphology_embedder is not None
            else MorphologyEmbedder()
        )
        morphology = self.morphology_embedder_.fit_transform(y)
        self.alignment_ = clone(
            self.alignment if self.alignment is not None else AlignmentEstimator()
        )
        self.alignment_.fit(text, morphology)
        self.retrieval_ = clone(
            self.retrieval if self.retrieval is not None else RetrievalEstimator()
        )
        if self.retrieval_.method == "exact_gene":
            raise ValueError(
                "Exact-gene lookup is an identity control; use it outside the morphology pipeline"
            )
        self.retrieval_.fit(self.morphology_embedder_.transform(gallery_y))
        self.evaluator_ = clone(self.evaluator if self.evaluator is not None else MetricEvaluator())
        self.train_metadata_ = X.copy()
        self.gallery_ = gallery.copy()
        return self

    def _queries(self, X):
        check_is_fitted(self, "gallery_")
        self.split_.validate(self.train_metadata_, X)
        if not X.split.eq("test").all():
            raise ValueError("Prediction queries must belong to the test partition")
        return self.query_policy_.transform(X)

    def predict(self, X):
        queries = self._queries(X)
        vectors = self.text_embedder_.transform(queries.rendered_text.tolist())
        return self.retrieval_.predict(self.alignment_.transform(vectors))

    def evaluate(self, X):
        queries = self._queries(X)
        return self.evaluator_.evaluate(self.predict(X), queries, self.gallery_, self.split_)

    def score(self, X, y=None):
        value = self.evaluate(X).summary["mAP"]
        if value is None:
            raise ValueError("No evaluable queries; inspect evaluate().exclusions")
        return value
