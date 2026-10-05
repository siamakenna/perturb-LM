"""Score-based AP, stable Hit/Recall ties, and query-ID paired uncertainty."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.metrics import average_precision_score

from perturb_lm.sklearn_api.datasets import present
from perturb_lm.sklearn_api.splits import SplitSpec, candidate_exclusions


@dataclass
class EvaluationResult:
    summary: dict
    per_query: pd.DataFrame
    exclusions: pd.DataFrame


class MetricEvaluator(BaseEstimator):
    """Stateless evaluator: evaluate, rather than a meaningless fit/transform."""

    def __init__(
        self, top_k: tuple[int, ...] = (1, 5, 10), retrieval_unit: str = "well", relevance=None
    ):
        self.top_k = top_k
        self.retrieval_unit = retrieval_unit
        self.relevance = relevance

    def evaluate(
        self, scores, queries: pd.DataFrame, candidates: pd.DataFrame, split: SplitSpec
    ) -> EvaluationResult:
        scores = np.asarray(scores, dtype=float)
        if scores.shape != (len(queries), len(candidates)) or not np.isfinite(scores).all():
            raise ValueError("Scores must be a finite query-by-candidate matrix")
        if not self.top_k or any(type(k) is not int or k < 1 for k in self.top_k):
            raise ValueError("top_k must contain positive integers")
        if self.retrieval_unit not in {"well", "treatment", "profile", "image"}:
            raise ValueError("Unsupported retrieval unit")
        label = "treatment"
        if self.relevance is not None:
            if self.retrieval_unit != self.relevance.retrieval_unit:
                raise ValueError("Evaluator unit differs from relevance contract")
            if tuple(split.exclude) != tuple(self.relevance.exclusions):
                raise ValueError("Evaluator exclusions differ from relevance contract")
            queries, candidates = (
                self.relevance.prepare(queries),
                self.relevance.prepare(candidates),
            )
            label = "relevance_identity"
            if (
                self.relevance.query_unit == "identity"
                and queries[label].dropna().duplicated().any()
            ):
                raise ValueError("Identity queries require one query per relevance identity")
        if (
            queries.empty
            or queries.query_id.duplicated().any()
            or not queries.query_id.map(present).all()
        ):
            raise ValueError("Queries require unique IDs")
        if candidates.record_id.duplicated().any() or not candidates.record_id.map(present).all():
            raise ValueError("Candidates require unique record IDs")
        complete_wells = np.ones(len(candidates), dtype=bool)
        if self.retrieval_unit in {"profile", "image"}:
            key = self.retrieval_unit + "_id"
            if key not in candidates or not candidates[key].map(present).all():
                raise ValueError(f"Missing {key} for retrieval unit")
            if candidates.duplicated(["dataset", key]).any():
                raise ValueError(f"Duplicate {key} candidates")
        if self.retrieval_unit == "well":
            from perturb_lm.sklearn_api.contracts import canonical_well

            candidates = candidates.copy()
            fields = ["dataset", "source", "batch", "plate", "well"]
            if any(f not in candidates for f in fields):
                raise ValueError("Well retrieval requires well identity columns")
            complete_wells = candidates[fields].apply(lambda col: col.map(present)).all(axis=1)
            candidates["well"] = candidates.well.map(canonical_well)
            if candidates.loc[complete_wells].duplicated(fields).any():
                raise ValueError(
                    "Aggregate images/profiles to one row per well before well retrieval"
                )
        rows, excluded = [], []
        for i, (_, query) in enumerate(queries.iterrows()):
            row = {"query_id": query.query_id, "n_positives": 0, "evaluable": False}
            reasons = candidate_exclusions(
                query,
                candidates,
                split,
                required_field=None if self.relevance is not None else "treatment",
            )
            reasons = [
                r if present(value) else (*r, "missing_candidate_relevance_identity")
                for r, value in zip(reasons, candidates[label], strict=True)
            ]
            reasons = [
                r if valid else (*r, "missing_well_identity")
                for r, valid in zip(reasons, complete_wells, strict=True)
            ]
            keep = np.array([not r for r in reasons], dtype=bool)
            for j, reason in enumerate(reasons):
                for code in reason:
                    excluded.append(
                        {
                            "query_id": query.query_id,
                            "candidate_id": candidates.iloc[j].record_id,
                            "reason": code,
                        }
                    )
            gallery = candidates.loc[keep].copy()
            gallery["score"] = scores[i, keep]
            if self.retrieval_unit == "treatment":
                # Filter constituent wells first; equal-weight mean score per treatment.
                gallery = gallery.groupby(label, as_index=False, sort=True).score.mean()
                gallery["record_id"] = gallery[label]
            reason = None
            if self.relevance is None and not present(query.get("treatment")):
                reason = "missing_query_treatment"
            if self.relevance is not None and not present(query.get(label)):
                reason = "missing_query_relevance_identity"
            positive = gallery[label].eq(query.get(label)).to_numpy()
            if reason is None and not positive.any():
                reason = "no_positive_after_filtering"
            row["n_candidates"] = len(gallery)
            row["n_positives"] = int(positive.sum())
            if reason:
                row["exclusion_reason"] = reason
                excluded.append(
                    {"query_id": query.query_id, "candidate_id": None, "reason": reason}
                )
            else:
                row.update(evaluable=True, exclusion_reason=None)
                row["average_precision"] = float(average_precision_score(positive, gallery.score))
                ranked = gallery.sort_values(["score", "record_id"], ascending=[False, True])
                ranked_positive = ranked[label].eq(query[label]).to_numpy()
                for k in self.top_k:
                    count = int(ranked_positive[:k].sum())
                    row[f"hit_at_{k}"] = float(count > 0)
                    row[f"recall_at_{k}"] = count / int(positive.sum())
            rows.append(row)
        per_query = pd.DataFrame(rows)
        metrics = [
            "average_precision",
            *[f"{m}_at_{k}" for k in self.top_k for m in ("hit", "recall")],
        ]
        summary = {
            "n_queries": len(queries),
            "n_evaluable_queries": int(per_query.evaluable.sum()),
            "n_excluded_queries": int((~per_query.evaluable).sum()),
        }
        for metric in metrics:
            if metric not in per_query:
                per_query[metric] = np.nan
            summary["mAP" if metric == "average_precision" else metric] = (
                float(per_query.loc[per_query.evaluable, metric].mean())
                if per_query.evaluable.any()
                else None
            )
        return EvaluationResult(
            summary,
            per_query,
            pd.DataFrame(excluded, columns=["query_id", "candidate_id", "reason"]),
        )


class QueryBootstrap(BaseEstimator):
    def __init__(self, n_resamples: int = 1000, confidence: float = 0.95, random_state: int = 0):
        self.n_resamples = n_resamples
        self.confidence = confidence
        self.random_state = random_state

    def evaluate(
        self,
        values: pd.DataFrame,
        reference: pd.DataFrame | None = None,
        metric: str = "average_precision",
    ) -> dict:
        if type(self.n_resamples) is not int or self.n_resamples < 1 or not 0 < self.confidence < 1:
            raise ValueError("Require positive integer resamples and 0 < confidence < 1")
        for frame in (values,) if reference is None else (values, reference):
            if not frame.query_id.map(present).all() or frame.query_id.duplicated().any():
                raise ValueError("Bootstrap requires one row per unique query ID, not seed rows")

        def eligible(frame):
            series = frame.set_index("query_id")[metric].sort_index().astype(float)
            if "evaluable" in frame:
                if not frame.evaluable.map(lambda x: isinstance(x, (bool, np.bool_))).all():
                    raise ValueError("evaluable must contain booleans")
                series = series.where(frame.set_index("query_id").evaluable)
            return series.where(np.isfinite(series))

        first = eligible(values)
        n_total = len(first)
        if reference is not None:
            second = eligible(reference)
            if set(first.index) != set(second.index):
                raise ValueError("Paired bootstrap requires identical query-ID populations")
            first = first - second
        finite = np.isfinite(first.to_numpy(dtype=float))
        data = first.to_numpy(dtype=float)[finite]
        if not len(data):
            raise ValueError("No evaluable paired queries for bootstrap")
        rng = np.random.default_rng(self.random_state)
        means = np.array(
            [rng.choice(data, size=len(data), replace=True).mean() for _ in range(self.n_resamples)]
        )
        tail = (1 - self.confidence) / 2
        low, high = np.quantile(means, [tail, 1 - tail])
        return {
            "estimate": float(data.mean()),
            "ci_low": float(low),
            "ci_high": float(high),
            "n_queries": n_total,
            "n_evaluable_queries": len(data),
            "n_excluded_queries": n_total - len(data),
            "paired": reference is not None,
            "n_resamples": self.n_resamples,
            "confidence": self.confidence,
            "random_state": self.random_state,
        }
