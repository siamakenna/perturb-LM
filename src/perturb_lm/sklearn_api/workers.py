"""Stage workers around validated local inputs; no network or implicit downloads."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from perturb_lm.sklearn_api.aggregation import aggregate_results
from perturb_lm.sklearn_api.contracts import RelevanceContract
from perturb_lm.sklearn_api.evaluation import MetricEvaluator, QueryBootstrap
from perturb_lm.sklearn_api.neural import NeuralProjection


def save_embedding_stage(
    embeddings: np.ndarray, record_ids, output: Path, provenance: dict
) -> Path:
    """Save a validated embedding artifact with a completion marker."""
    embeddings = np.asarray(embeddings)
    record_ids = np.asarray(record_ids, dtype=str)
    if (
        embeddings.ndim != 2
        or len(record_ids) != len(embeddings)
        or len(set(record_ids)) != len(record_ids)
    ):
        raise ValueError("Embedding worker requires a 2-D matrix and unique aligned record IDs")
    if not np.isfinite(embeddings).all():
        raise ValueError("Embedding worker received nonfinite values")
    output = Path(output)
    working = output.with_name(output.name + ".working")
    if working.exists():
        raise ValueError("Incomplete embedding output exists; quarantine before retry")
    working.mkdir(parents=True)
    try:
        np.savez_compressed(
            working / "embeddings.npz", embeddings=embeddings, record_ids=record_ids
        )
        manifest = {
            "provenance": provenance,
            "n_rows": len(embeddings),
            "dimension": embeddings.shape[1],
            "complete": True,
        }
        (working / "complete.json").write_text(json.dumps(manifest, indent=2) + "\n")
        if output.exists():
            raise FileExistsError(f"Embedding output already exists: {output}")
        working.rename(output)
    except BaseException:
        import shutil

        shutil.rmtree(working, ignore_errors=True)
        raise
    return output


def fit_alignment_stage(
    text, morphology, *, method="ridge", group_ids=None, output: Path | None = None, **params
):
    model = (
        NeuralProjection(**params)
        if method in {"mlp_projection", "contrastive_projection"}
        else None
    )
    if model is not None:
        model.objective = "contrastive" if method == "contrastive_projection" else "mse"
    else:
        from perturb_lm.sklearn_api.estimators import AlignmentEstimator

        model = AlignmentEstimator(method=method, **params)
    model.fit(text, morphology, group_ids=group_ids) if method in {
        "mlp_projection",
        "contrastive_projection",
    } else model.fit(text, morphology)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        # Pickle is intentionally limited to learned local state and must remain ignored output.
        import pickle

        temporary = output.with_suffix(output.suffix + ".working")
        with temporary.open("wb") as handle:
            pickle.dump(model, handle)
        temporary.replace(output)
    return model


def evaluate_retrieval_stage(
    scores,
    queries,
    candidates,
    split,
    *,
    contract=None,
    top_k=(1, 5, 10),
    output=None,
    provenance=None,
):
    if contract is not None:
        if not isinstance(contract, RelevanceContract):
            raise TypeError("contract must be a RelevanceContract")
        contract.validate_split(queries, candidates, split)
    evaluator = MetricEvaluator(
        tuple(top_k), contract.retrieval_unit if contract else "well", contract
    )
    result = evaluator.evaluate(scores, queries, candidates, split)
    if output is not None:
        aggregate_results(
            result.per_query,
            exclusions=result.exclusions,
            provenance=provenance or {},
            output=output,
        )
    return result


def bootstrap_stage(per_query, *, baseline=None, n_resamples=5000, seed=0, output=None):
    result = QueryBootstrap(n_resamples=n_resamples, random_state=seed).evaluate(
        per_query, baseline, metric="average_precision"
    )
    if output is not None:
        Path(output).write_text(json.dumps(result, indent=2) + "\n")
    return result
