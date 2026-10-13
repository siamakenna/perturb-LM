"""Public API contracts, also copied into fresh artifact-only environments."""

import copy
import importlib.metadata
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.base import clone
from sklearn.exceptions import NotFittedError
from sklearn.pipeline import Pipeline

from perturb_lm import __version__
from perturb_lm.resources import policy_document
from perturb_lm.sklearn_api import (
    AlignmentEstimator,
    BenchmarkPipeline,
    MorphologyEmbedder,
    RetrievalEstimator,
    TfidfTextEmbedder,
    asset_catalog,
)
from perturb_lm.sklearn_api.planning import load_relevance_contracts


def test_installed_version_resources_and_optional_imports():
    assert __version__ == importlib.metadata.version("perturb-lm")
    assert policy_document("relevance_contracts")["schema_version"] == 1
    assert load_relevance_contracts()["M5_LEAKAGE_CONTROL"].approval == "proposed"
    assert asset_catalog()["dinov2"].input_kind == "image"
    if os.environ.get("PLM_EXPECT_INSTALLED") == "1":
        import perturb_lm

        assert Path(perturb_lm.__file__).is_relative_to(Path(sys.prefix))
    # New interpreter makes this independent of other tests importing optional backends.
    subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; import perturb_lm; import perturb_lm.sklearn_api; "
            "assert not {'torch', 'transformers', 'skimage', 'tifffile'} & sys.modules.keys()",
        ],
        check=True,
    )


@pytest.mark.parametrize(
    "model,data,targets,method",
    [
        (MorphologyEmbedder(), [[1.0, 2.0], [3.0, 4.0]], None, "transform"),
        (TfidfTextEmbedder(), ["vesicle transport", "nuclear shape"], None, "transform"),
        (AlignmentEstimator(), [[1.0, 2.0], [3.0, 4.0]], [[2.0, 1.0], [4.0, 3.0]], "predict"),
        (RetrievalEstimator(), [[1.0, 2.0], [3.0, 4.0]], None, "predict"),
    ],
)
def test_cloning_fit_state_and_row_order(model, data, targets, method):
    with pytest.raises(NotFittedError):
        getattr(model, method)(data)
    fitted = clone(model).fit(data, targets)
    snapshot = copy.deepcopy(fitted.__dict__)
    expected = getattr(fitted, method)(data)
    reordered = getattr(fitted, method)(data[::-1])

    def dense(value):
        return value.toarray() if hasattr(value, "toarray") else value

    np.testing.assert_allclose(dense(reordered), dense(expected)[::-1])
    # Numeric state and serialized fitted state must remain unchanged at inference.
    import pickle

    assert pickle.dumps(snapshot) == pickle.dumps(fitted.__dict__)
    assert not any(k.endswith("_") for k in clone(fitted).__dict__)


@pytest.mark.parametrize(
    "model,data,targets,parameter,value",
    [
        (MorphologyEmbedder(), [[1.0, 2.0], [3.0, 4.0]], None, "standardize", False),
        (TfidfTextEmbedder(), ["vesicle transport", "nuclear shape"], None, "analyzer", "char"),
        (AlignmentEstimator(), [[1.0, 2.0], [3.0, 4.0]], [[2.0, 1.0], [4.0, 3.0]], "method", "pls"),
        (RetrievalEstimator(), [[1.0, 2.0], [3.0, 4.0]], None, "method", "random"),
    ],
)
def test_changed_parameters_require_reference_refit(model, data, targets, parameter, value):
    model.fit(data, targets).set_params(**{parameter: value})
    operation = model.transform if hasattr(model, "transform") else model.predict
    with pytest.raises(ValueError, match="Parameters changed"):
        operation(data)


def test_train_only_morphology_pipeline_validation_and_failed_refit():
    reference = pd.DataFrame({"area": [1.0, 2.0, 3.0], "texture": [2.0, 4.0, 6.0]})
    query = pd.DataFrame({"area": [100.0], "texture": [500.0]})
    pipeline = Pipeline([("morphology", MorphologyEmbedder()), ("gallery", RetrievalEstimator())])
    pipeline.fit(reference)
    scaler = pipeline.named_steps["morphology"].scaler_
    np.testing.assert_allclose(scaler.mean_, reference.mean())
    before = scaler.mean_.copy()
    assert pipeline.predict(query).shape == (1, 3)
    np.testing.assert_array_equal(before, scaler.mean_)
    with pytest.raises(ValueError, match="column order"):
        pipeline.predict(query[["texture", "area"]])
    with pytest.raises(ValueError):
        pipeline.predict([[float("nan"), 1.0]])
    model = MorphologyEmbedder().fit(reference)
    with pytest.raises(ValueError):
        model.fit([[float("nan"), 1.0]])
    with pytest.raises(NotFittedError):
        model.transform(reference)


def test_alignment_targets_and_retrieval_labels_are_separate():
    with pytest.raises(ValueError):
        AlignmentEstimator().fit([[1.0, 2.0], [3.0, 4.0]], ["treatment-a", "treatment-b"])
    gallery = np.eye(2)
    first = RetrievalEstimator().fit(gallery, ["a", "b"]).predict(gallery)
    second = RetrievalEstimator().fit(gallery, ["different", "labels"]).predict(gallery)
    np.testing.assert_array_equal(first, second)
    assert not hasattr(AlignmentEstimator(), "score")
    assert not hasattr(RetrievalEstimator(), "score")
    with pytest.raises(ValueError, match="retrieval mAP"):
        BenchmarkPipeline().score(None, [1, 2])


def test_retrieval_owns_gallery_and_rejects_bad_dimensions():
    gallery = np.array(["gene-a", "gene-b"])
    model = RetrievalEstimator("exact_gene").fit(gallery)
    gallery[0] = "changed"
    assert model.predict(["gene-a"])[0, 0] == 1
    with pytest.raises(ValueError, match="dimension"):
        RetrievalEstimator("random").fit(np.eye(2)).predict([[1, 2, 3]])


def test_pipeline_rejects_misordered_target_indices():
    train = pd.DataFrame({"split": ["train", "train"]}, index=[10, 20])
    gallery = pd.DataFrame({"split": ["test", "test"]}, index=[30, 40])
    targets = pd.DataFrame([[1.0, 2.0], [3.0, 4.0]], index=[20, 10])
    with pytest.raises(ValueError, match="target indices"):
        BenchmarkPipeline().fit(train, targets, gallery=gallery, gallery_y=np.eye(2))
