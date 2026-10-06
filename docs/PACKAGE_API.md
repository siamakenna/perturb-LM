# Perturb-LM alpha package API

Install the built wheel or sdist, then use imports from `perturb_lm.sklearn_api`.
The alpha candidate supports Python 3.10–3.12 and scikit-learn >=1.4,<2.
CI checks 1.4.2 on Python 3.10 and the current resolved version on 3.11/3.12.
This is bounded compatibility coverage, not every possible dependency combination.

The following complete example is executed outside the checkout against both
artifacts, in base and pixel environments. All data are synthetic.

```python
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.pipeline import Pipeline
from perturb_lm.sklearn_api import (
    BenchmarkPipeline, MorphologyEmbedder, RetrievalEstimator,
    TfidfTextEmbedder,
)

# Ordinary sklearn pipeline: fit scaling and the gallery on references only.
reference = np.array([[1., 2.], [2., 4.], [4., 3.]])
query = np.array([[2., 3.]])
model = Pipeline([
    ("morphology", MorphologyEmbedder()),
    ("retrieval", RetrievalEstimator()),
])
model.fit(reference)
before = model["morphology"].scaler_.mean_.copy()
assert model.predict(query).shape == (1, 3)  # columns retain reference row order
np.testing.assert_array_equal(before, model["morphology"].scaler_.mean_)
assert clone(model).get_params()["retrieval__method"] == "cosine"

# Paired metadata/morphology benchmark: y contains numeric regression targets.
# Treatment labels remain evaluator metadata, outside the numeric targets.
def metadata(prefix, partition, plates, wells):
    return pd.DataFrame({
        "dataset": ["synthetic"] * 4, "source": ["source-a"] * 4,
        "batch": ["batch-a"] * 4, "plate": plates, "well": wells,
        "record_id": [f"{prefix}-{i}" for i in range(4)],
        "treatment": ["treat-a", "treat-b", "treat-a", "treat-b"],
        "Metadata_pert_type": ["vesicle response", "nuclear response"] * 2,
        "split": [partition] * 4,
    })

train = metadata("train", "train", ["plate-train"] * 4, ["A01", "A02", "A03", "A04"])
gallery = metadata("test", "test", ["plate-x", "plate-x", "plate-y", "plate-y"],
                   ["B01", "B02", "C01", "C02"])
targets = np.array([[1., 0.], [0., 1.], [1.1, .1], [.1, 1.1]])
benchmark = BenchmarkPipeline(text_embedder=TfidfTextEmbedder(), synthetic=True)
benchmark.fit(train, targets, gallery=gallery, gallery_y=targets + .2)
scores = benchmark.predict(gallery)
assert scores.shape == (4, 4)
result = benchmark.evaluate(gallery)
assert result.summary["n_evaluable_queries"] == 4
assert benchmark.score(gallery) == result.summary["mAP"]
np.testing.assert_allclose(
    benchmark.predict(gallery.iloc[::-1]), scores[::-1]
)
```

`AlignmentEstimator.fit(X, y)` requires paired numeric morphology targets,
not retrieval labels. DataFrame target indices must match metadata row order
in `BenchmarkPipeline.fit`; arrays follow positional order. Numeric
morphology DataFrames also retain their feature-column contract.

`RetrievalEstimator.predict` returns query-by-gallery similarity scores.
It deliberately has no default regression/classification `score`.
`BenchmarkPipeline.score(X)` returns retrieval mAP; use `evaluate(X)` for
evaluable counts and explicit exclusions. Passing regression targets to
`score` raises. Undefined AP is excluded and reported, never replaced by zero.
Changing fitted primitive estimator parameters requires reference/training refit.
Cloning produces an unfitted estimator. Inference preserves fitted statistics.

Image analysis uses the existing CLI and `PixelMorphologyTransformer`, described
in [the executed image example](PIXEL_PACKAGE_EXAMPLE.md) and
[full command reference](PIXEL_ONLY_MVP.md). The pixel extra is optional.
Torch/Transformers and image dependencies are not imported by the base API.
Model assets are never downloaded implicitly.

Relevance and model-asset YAML snapshots ship inside both distributions, with
byte-parity tests against reviewed repository configuration. Changing the
source contracts requires updating the packaged snapshots in the same reviewed
change. Historical contracts and production execution gates remain in force.
Repository planning/Slurm scripts and frozen-result verification still require
an explicit source checkout; the installed estimator/image API does not.
