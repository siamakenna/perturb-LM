"""Dependency-light model input contracts; real forward passes are tested separately."""

import json
from dataclasses import replace

import numpy as np
import pytest
from sklearn.base import clone

from perturb_lm.sklearn_api import ImagePreprocessing, LocalModelEmbedder, asset_catalog
from perturb_lm.sklearn_api.datasets import file_checksum


def preprocessing():
    return ImagePreprocessing(
        input_channels=("c0", "c1", "c2", "c3"),
        model_channels=("c2", "c0", "c3"),
        input_range=(0.0, 100.0),
        mean=(0.5, 0.4, 0.3),
        std=(0.2, 0.3, 0.4),
    )


@pytest.mark.parametrize(
    "change",
    [
        {"model_channels": ("c0", "c0", "c1")},
        {"model_channels": ("c0", "c1", "unknown")},
        {"input_channels": ("c0", "c0", "c2", "c3")},
        {"input_range": (1.0, 1.0)},
        {"input_range": (0.0, np.nan)},
        {"std": (0.0, 1.0, 1.0)},
        {"mean": [0.0, 0.0, 0.0]},
    ],
)
def test_reject_ambiguous_preprocessing(change):
    with pytest.raises(ValueError):
        replace(preprocessing(), **change).validate()


@pytest.mark.parametrize(
    "pixels",
    [
        np.zeros((1, 3, 8, 8)),
        np.zeros((1, 8, 8, 4)),
        np.zeros((1, 4, 0, 8)),
        np.full((1, 4, 8, 8), np.nan),
        np.full((1, 4, 8, 8), np.inf),
        np.full((1, 4, 8, 8), 101.0),
        np.full((1, 4, 8, 8), -1.0),
    ],
)
def test_reject_bad_image_schema_or_range(pixels):
    with pytest.raises(ValueError):
        preprocessing().validate_input(pixels)


def test_dinov2_requires_explicit_contract_before_optional_loading(tmp_path):
    spec = asset_catalog()["dinov2"]
    (tmp_path / "fixture").write_bytes(b"synthetic validation-only fixture")
    (tmp_path / "asset.json").write_text(
        json.dumps(
            {
                "identifier": spec.identifier,
                "revision": spec.revision,
                "complete": True,
                "checksums": {"fixture": file_checksum(tmp_path / "fixture")},
            }
        )
    )
    pixels = np.zeros((1, 4, 8, 8))
    with pytest.raises(ValueError, match="explicit ImagePreprocessing"):
        LocalModelEmbedder(spec, tmp_path).fit(pixels)
    model = LocalModelEmbedder(spec, tmp_path, image_preprocessing=preprocessing()).fit(pixels)
    assert clone(model).image_preprocessing == preprocessing()
    model.set_params(image_preprocessing=replace(preprocessing(), mean=(0.0, 0.0, 0.0)))
    with pytest.raises(ValueError, match="parameters changed"):
        model.transform(pixels)


def test_scibert_reuses_pinned_offline_hf_text_contract():
    from perturb_lm.sklearn_api.registry import REGISTRY

    spec = asset_catalog()["scibert"]
    assert spec.identifier == "allenai/scibert_scivocab_uncased"
    assert spec.revision == "952d056ace307abd2cda7cee822a1d608deb20ed"
    assert spec.backend == "hf_text"
    assert spec.dimension == 768
    assert spec.input_kind == "text"
    assert spec.pooling == "mean"
    assert spec.normalize is True
    assert spec.max_length == 512
    assert REGISTRY["scibert"].identifier == spec.identifier
    spec.validate()
