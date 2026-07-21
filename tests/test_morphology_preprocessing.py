from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from perturb_lm.modeling.integrity import validate_preprocessor_fit_scope
from perturb_lm.modeling.preprocessing import (
    MorphologyPreprocessor,
    load_morphology_preprocessor,
)


def _train_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Cells_b": [1.0, 3.0, 5.0],
            "Cells_a": [10.0, np.nan, 14.0],
            "Cells_zero": [2.0, 2.0, 2.0],
            "Cells_all_missing": [np.nan, np.nan, np.nan],
            "Cells_near_zero": [1.0, 1.0 + 1e-8, 1.0 + 2e-8],
            "Metadata_Plate": ["p1", "p1", "p2"],
        }
    )


def test_preprocessor_fits_train_only_and_uses_deterministic_feature_order() -> None:
    train = _train_frame()
    test_a = pd.DataFrame({"Cells_a": [1000.0], "Cells_b": [1000.0], "Metadata_Plate": ["p9"]})
    test_b = pd.DataFrame({"Cells_a": [-1000.0], "Cells_b": [-1000.0], "Metadata_Plate": ["p8"]})

    pre = MorphologyPreprocessor().fit(train, fit_split="train")
    transformed_a = pre.transform(test_a)
    transformed_b = pre.transform(test_b)

    assert pre.feature_columns_ == ["Cells_a", "Cells_b"]
    assert pre.imputer_.statistics_.tolist() == [12.0, 3.0]
    assert transformed_a.shape == (1, 2)
    assert transformed_b.shape == (1, 2)
    assert np.allclose(pre.scaler_.mean_, [12.0, 3.0])


def test_preprocessor_repeated_runs_and_save_load_are_identical(tmp_path) -> None:
    train = _train_frame()
    test = pd.DataFrame({"Cells_a": [12.0], "Cells_b": [3.0]})

    pre_a = MorphologyPreprocessor().fit(train)
    pre_b = MorphologyPreprocessor().fit(train)
    assert np.allclose(pre_a.transform(test), pre_b.transform(test))

    path = tmp_path / "outputs" / "preprocessing" / "morphology_preprocessor.pkl"
    pre_a.save(path)
    loaded = load_morphology_preprocessor(path)
    assert np.allclose(pre_a.transform(test), loaded.transform(test))


def test_preprocessor_missing_required_or_fitted_features_fail() -> None:
    train = _train_frame()
    with pytest.raises(ValueError, match="Required morphology features are missing"):
        MorphologyPreprocessor().fit(train, required_features=["Cells_missing_required"])

    pre = MorphologyPreprocessor().fit(train)
    with pytest.raises(ValueError, match="Transform data is missing"):
        pre.transform(pd.DataFrame({"Cells_a": [1.0]}))


def test_preprocessor_extra_columns_policy_and_output_path_guard(tmp_path) -> None:
    train = _train_frame()
    with pytest.raises(ValueError, match="Unexpected extra morphology features"):
        MorphologyPreprocessor(extra_columns_policy="error").fit(
            train,
            feature_columns=["Cells_a", "Cells_b"],
        )

    pre = MorphologyPreprocessor().fit(train)
    with pytest.raises(ValueError, match="ignored output directories"):
        pre.save("not_ignored/preprocessor.pkl")


def test_preprocessor_fit_scope_integrity_report() -> None:
    pre = MorphologyPreprocessor().fit(_train_frame(), fit_split="train")
    report = validate_preprocessor_fit_scope(pre)

    assert report.ok
