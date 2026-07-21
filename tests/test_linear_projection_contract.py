from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from perturb_lm.modeling.linear_projection import (
    LinearProjectionContract,
    load_linear_projection_contract,
    make_synthetic_projection_fixture,
    run_synthetic_projection_contract,
)
from perturb_lm.modeling.preprocessing import MorphologyPreprocessor


def test_synthetic_projection_contract_is_deterministic_and_learnable(tmp_path: Path) -> None:
    summary_a = run_synthetic_projection_contract(
        out_dir=tmp_path / "outputs" / "projection_a",
        seed=0,
        learnable=True,
    )
    summary_b = run_synthetic_projection_contract(
        out_dir=tmp_path / "outputs" / "projection_b",
        seed=0,
        learnable=True,
    )

    assert summary_a["projection"] == summary_b["projection"]
    assert summary_a["projection"]["mean_average_precision"] > summary_a["random"][
        "mean_average_precision"
    ]
    assert summary_a["projection"]["hit_at_1"] == 1.0
    assert summary_a["preprocessing_fit_scope"] == "train"
    assert summary_a["projection_fit_scope"] == "train"


def test_synthetic_projection_random_fixture_does_not_falsely_improve(tmp_path: Path) -> None:
    summary = run_synthetic_projection_contract(
        out_dir=tmp_path / "outputs" / "projection_random",
        seed=0,
        learnable=False,
    )

    assert summary["projection"]["mean_average_precision"] <= summary["random"][
        "mean_average_precision"
    ]


def test_linear_projection_dimensions_and_save_load_round_trip(tmp_path: Path) -> None:
    profiles, text = make_synthetic_projection_fixture(seed=2)
    features = [column for column in profiles.columns if column.startswith("Cells_feature_")]
    text_columns = [column for column in text.columns if column.startswith("text_")]
    train_profiles = profiles[profiles["split"] == "train"].reset_index(drop=True)
    train_text = text[text["split"] == "train"].set_index("treatment")[text_columns]
    repeated_text = np.vstack(
        [
            train_text.loc[treatment].to_numpy(dtype=float)
            for treatment in train_profiles["treatment"]
        ]
    )
    preprocessor = MorphologyPreprocessor().fit(
        train_profiles,
        feature_columns=features,
        fit_split="train",
    )
    targets = preprocessor.transform(train_profiles)
    projection = LinearProjectionContract().fit(repeated_text, targets, fit_split="train")

    assert projection.input_dim_ == len(text_columns)
    assert projection.output_dim_ == len(preprocessor.feature_columns_)

    path = tmp_path / "outputs" / "projection" / "weights.npz"
    projection.save(path)
    loaded = load_linear_projection_contract(path)
    assert np.allclose(projection.transform(repeated_text), loaded.transform(repeated_text))


def test_linear_projection_safe_output_policy() -> None:
    with pytest.raises(ValueError, match="ignored output directories"):
        LinearProjectionContract().save("not_ignored/weights.npz")


def test_phase3b_projection_smoke_cli_writes_safe_summary(tmp_path: Path) -> None:
    out = tmp_path / "outputs" / "projection_cli"
    subprocess.run(
        [
            sys.executable,
            "scripts/run_phase3b_projection_smoke.py",
            "--out",
            str(out),
            "--seed",
            "0",
        ],
        check=True,
    )

    summary_text = (out / "phase3b_projection_smoke_summary.json").read_text()
    summary = json.loads(summary_text)
    assert summary["projection"]["mean_average_precision"] == 1.0
    assert "profile-" not in summary_text
    assert "treatment-" not in summary_text
