"""Deterministic NumPy projection heads with checksummed, non-pickle checkpoints."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.utils.validation import check_array, check_is_fitted


def unit_rows(values):
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    return values / np.maximum(norms, 1e-12), norms


class NeuralProjection(TransformerMixin, BaseEstimator):
    """A two-layer ReLU MLP: MSE regression or multi-positive contrastive loss.

    Every epoch is a full-batch deterministic gradient step. No evaluation rows,
    early stopping, or implicit validation split are accepted. group_ids identify
    equivalent training targets for contrastive positives (no false negatives
    between training replicates). Checkpoints support exact epoch continuation.
    """

    def __init__(
        self,
        objective="mse",
        hidden_dim=32,
        epochs=100,
        learning_rate=0.01,
        temperature=0.1,
        random_state=0,
    ):
        self.objective = objective
        self.hidden_dim = hidden_dim
        self.epochs = epochs
        self.learning_rate = learning_rate
        self.temperature = temperature
        self.random_state = random_state

    def fit(self, X, y, *, group_ids=None, checkpoint=None):
        X, y = check_array(X), check_array(y)
        if (
            len(X) != len(y)
            or len(X) < 3
            or not np.any(np.std(X, axis=0) > 1e-12)
            or not np.any(np.std(y, axis=0) > 1e-12)
        ):
            raise ValueError("Degenerate or unpaired training data for neural alignment")
        if (
            self.objective not in {"mse", "contrastive"}
            or self.hidden_dim < 1
            or self.epochs < 1
            or self.learning_rate <= 0
            or self.temperature <= 0
        ):
            raise ValueError("Invalid neural projection parameters")
        if self.objective == "contrastive" and group_ids is None:
            raise ValueError(
                "Contrastive alignment requires explicit training relevance identities"
            )
        groups = np.asarray(group_ids if group_ids is not None else np.arange(len(X)), dtype=str)
        if groups.shape != (len(X),) or (self.objective == "contrastive" and len(set(groups)) < 2):
            raise ValueError("Contrastive training requires at least two distinct relevance groups")
        self.n_features_in_, self.n_outputs_ = X.shape[1], y.shape[1]
        settings = {k: v for k, v in self.get_params().items() if k != "epochs"}
        fingerprint = hashlib.sha256(
            X.tobytes()
            + y.tobytes()
            + json.dumps(groups.tolist()).encode()
            + json.dumps(settings, sort_keys=True).encode()
        ).hexdigest()
        rng = np.random.default_rng(self.random_state)
        self.weights_ = [
            rng.normal(0, 1 / np.sqrt(X.shape[1]), (X.shape[1], self.hidden_dim)),
            np.zeros(self.hidden_dim),
            rng.normal(0, 1 / np.sqrt(self.hidden_dim), (self.hidden_dim, y.shape[1])),
            np.zeros(y.shape[1]),
        ]
        start = 0
        if checkpoint is not None and Path(checkpoint).exists():
            with np.load(checkpoint, allow_pickle=False) as saved:
                if str(saved["fingerprint"].item()) != fingerprint:
                    raise ValueError("Checkpoint differs from training data or hyperparameters")
                self.weights_ = [saved[f"w{i}"].copy() for i in range(4)]
                start = int(saved["epoch"].item())
            if start > self.epochs:
                raise ValueError("Checkpoint has more epochs than requested")
        target, _ = unit_rows(y)
        positives = groups[:, None] == groups[None, :]
        distribution = positives / positives.sum(axis=1, keepdims=True)
        for epoch in range(start, self.epochs):
            w1, b1, w2, b2 = self.weights_
            hidden_raw = X @ w1 + b1
            hidden = np.maximum(hidden_raw, 0)
            prediction = hidden @ w2 + b2
            if self.objective == "mse":
                gradient = 2 * (prediction - y) / prediction.size
                loss = np.mean((prediction - y) ** 2)
            else:
                normalized, norms = unit_rows(prediction)
                logits = normalized @ target.T / self.temperature
                logits -= logits.max(axis=1, keepdims=True)
                probability = np.exp(logits)
                probability /= probability.sum(axis=1, keepdims=True)
                loss = -np.sum(distribution * np.log(np.maximum(probability, 1e-12))) / len(X)
                grad_normal = (probability - distribution) @ target / (len(X) * self.temperature)
                gradient = (
                    grad_normal
                    - normalized * np.sum(grad_normal * normalized, axis=1, keepdims=True)
                ) / np.maximum(norms, 1e-12)
            grad_hidden = (gradient @ w2.T) * (hidden_raw > 0)
            gradients = [
                X.T @ grad_hidden,
                grad_hidden.sum(axis=0),
                hidden.T @ gradient,
                gradient.sum(axis=0),
            ]
            self.weights_ = [
                weight - self.learning_rate * np.clip(grad, -10, 10)
                for weight, grad in zip(self.weights_, gradients, strict=True)
            ]
            if not all(np.isfinite(w).all() for w in self.weights_):
                raise ValueError("Nonfinite neural training state; review scaling/learning rate")
            if checkpoint is not None:
                path = Path(checkpoint)
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_suffix(".working.npz")
                np.savez(
                    temporary,
                    **{f"w{i}": value for i, value in enumerate(self.weights_)},
                    fingerprint=fingerprint,
                    epoch=epoch + 1,
                )
                temporary.replace(path)
        self.state_metadata_ = {
            "objective": self.objective,
            "seed": self.random_state,
            "epochs": self.epochs,
            "input_dimension": self.n_features_in_,
            "output_dimension": self.n_outputs_,
            "training_fingerprint": fingerprint,
            "fit_scope": "train",
            "final_loss": float(loss) if start < self.epochs else None,
        }
        return self

    def transform(self, X):
        check_is_fitted(self, "weights_")
        X = check_array(X)
        if X.shape[1] != self.n_features_in_:
            raise ValueError("Neural projection input dimension mismatch")
        w1, b1, w2, b2 = self.weights_
        return np.maximum(X @ w1 + b1, 0) @ w2 + b2

    def predict(self, X):
        return self.transform(X)
