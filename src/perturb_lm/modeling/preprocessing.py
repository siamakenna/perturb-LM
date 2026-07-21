"""Train-only preprocessing for morphology/profile feature matrices."""

from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from perturb_lm.data.jump import CELL_PAINTING_FEATURE_PREFIXES, detect_numeric_feature_columns

IGNORED_OUTPUT_ROOTS = {"outputs", "results", "models"}


@dataclass
class MorphologyPreprocessor(BaseEstimator, TransformerMixin):
    """Select, clean, impute, and scale morphology features using train data only."""

    near_zero_variance_threshold: float = 1e-12
    allowed_prefixes: tuple[str, ...] = CELL_PAINTING_FEATURE_PREFIXES
    extra_columns_policy: str = "ignore"
    feature_columns_: list[str] = field(default_factory=list, init=False)
    dropped_features_: dict[str, list[str]] = field(default_factory=dict, init=False)
    imputer_: SimpleImputer | None = field(default=None, init=False)
    scaler_: StandardScaler | None = field(default=None, init=False)
    fit_metadata_: dict[str, Any] = field(default_factory=dict, init=False)

    def fit(
        self,
        frame: pd.DataFrame,
        y: object | None = None,
        *,
        feature_columns: list[str] | None = None,
        required_features: list[str] | None = None,
        fit_split: str = "train",
    ) -> MorphologyPreprocessor:
        _ = y
        if self.extra_columns_policy not in {"ignore", "error"}:
            raise ValueError("extra_columns_policy must be 'ignore' or 'error'.")
        selected = self._select_feature_columns(frame, feature_columns)
        required = list(required_features or [])
        missing_required = sorted(set(required).difference(frame.columns))
        if missing_required:
            raise ValueError(f"Required morphology features are missing: {missing_required}")
        if self.extra_columns_policy == "error":
            unexpected = sorted(set(self._detect_allowed_numeric(frame)).difference(selected))
            if unexpected:
                raise ValueError(f"Unexpected extra morphology features are present: {unexpected}")
        matrix = _coerce_feature_frame(frame, selected)
        kept, dropped = _filter_features(
            matrix,
            near_zero_variance_threshold=self.near_zero_variance_threshold,
        )
        if not kept:
            raise ValueError("No usable morphology features remain after preprocessing filters.")
        self.feature_columns_ = kept
        self.dropped_features_ = dropped
        train_matrix = matrix[kept].replace([np.inf, -np.inf], np.nan).to_numpy(dtype=float)
        self.imputer_ = SimpleImputer(strategy="median")
        imputed = self.imputer_.fit_transform(train_matrix)
        self.scaler_ = StandardScaler()
        self.scaler_.fit(imputed)
        self.fit_metadata_ = {
            "fit_split": fit_split,
            "n_fit_rows": int(len(frame)),
            "n_input_features": int(len(selected)),
            "n_output_features": int(len(kept)),
            "dropped_feature_counts": {
                reason: len(columns) for reason, columns in self.dropped_features_.items()
            },
            "extra_columns_policy": self.extra_columns_policy,
        }
        return self

    def transform(self, frame: pd.DataFrame) -> np.ndarray:
        if self.imputer_ is None or self.scaler_ is None or not self.feature_columns_:
            raise ValueError("MorphologyPreprocessor must be fitted before transform.")
        missing = sorted(set(self.feature_columns_).difference(frame.columns))
        if missing:
            raise ValueError(f"Transform data is missing fitted morphology features: {missing}")
        matrix = (
            _coerce_feature_frame(frame, self.feature_columns_)
            .replace([np.inf, -np.inf], np.nan)
            .to_numpy(dtype=float)
        )
        return self.scaler_.transform(self.imputer_.transform(matrix))

    def fit_transform(
        self,
        frame: pd.DataFrame,
        y: object | None = None,
        **fit_params: Any,
    ) -> np.ndarray:
        return self.fit(frame, y, **fit_params).transform(frame)

    def save(self, path: Path | str) -> None:
        path = Path(path)
        _validate_ignored_output_path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as handle:
            pickle.dump(self, handle)

    def _select_feature_columns(
        self,
        frame: pd.DataFrame,
        feature_columns: list[str] | None,
    ) -> list[str]:
        if feature_columns is not None:
            return list(dict.fromkeys(feature_columns))
        detected, _ = detect_numeric_feature_columns(frame)
        allowed = [
            column
            for column in detected
            if str(column).startswith(self.allowed_prefixes)
            and pd.api.types.is_numeric_dtype(frame[column])
        ]
        return sorted(dict.fromkeys(allowed))

    def _detect_allowed_numeric(self, frame: pd.DataFrame) -> list[str]:
        return sorted(
            str(column)
            for column in frame.columns
            if str(column).startswith(self.allowed_prefixes)
            and pd.api.types.is_numeric_dtype(frame[column])
        )


def load_morphology_preprocessor(path: Path | str) -> MorphologyPreprocessor:
    """Load a fitted morphology preprocessor and verify its type."""

    with Path(path).open("rb") as handle:
        loaded = pickle.load(handle)
    if not isinstance(loaded, MorphologyPreprocessor):
        raise TypeError("Serialized object is not a MorphologyPreprocessor.")
    return loaded


def _coerce_feature_frame(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    if not columns:
        return pd.DataFrame(index=frame.index)
    missing = sorted(set(columns).difference(frame.columns))
    if missing:
        raise ValueError(f"Morphology feature columns are missing: {missing}")
    return frame.loc[:, columns].apply(pd.to_numeric, errors="coerce")


def _filter_features(
    matrix: pd.DataFrame,
    *,
    near_zero_variance_threshold: float,
) -> tuple[list[str], dict[str, list[str]]]:
    dropped: dict[str, list[str]] = {
        "all_missing": [],
        "zero_variance": [],
        "near_zero_variance": [],
    }
    if matrix.empty:
        return [], dropped
    clean = matrix.replace([np.inf, -np.inf], np.nan)
    variances = clean.var(axis=0, skipna=True, ddof=0)
    all_missing = clean.isna().all(axis=0)
    for column in clean.columns:
        if bool(all_missing[column]):
            dropped["all_missing"].append(str(column))
        elif float(variances[column]) == 0.0:
            dropped["zero_variance"].append(str(column))
        elif 0.0 < float(variances[column]) <= near_zero_variance_threshold:
            dropped["near_zero_variance"].append(str(column))
    dropped_set = set().union(*[set(values) for values in dropped.values()])
    kept = [str(column) for column in clean.columns if str(column) not in dropped_set]
    return kept, dropped


def _validate_ignored_output_path(path: Path) -> None:
    parts = [part for part in path.parts if part not in {".", ""}]
    if not parts:
        raise ValueError("A preprocessing output path is required.")
    if path.is_absolute():
        allowed = any(part in IGNORED_OUTPUT_ROOTS for part in parts)
    else:
        allowed = parts[0] in IGNORED_OUTPUT_ROOTS
    if not allowed:
        raise ValueError(
            "Fitted preprocessing objects must be saved under ignored output directories "
            f"({sorted(IGNORED_OUTPUT_ROOTS)})."
        )
