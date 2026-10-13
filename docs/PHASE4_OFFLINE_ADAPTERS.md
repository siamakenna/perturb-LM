# Offline DINOv2 and SapBERT adapter implementation

Related to #55; follows examination contracts #62 and stays separate from the
validated alpha candidate #61. This change does not alter that candidate's
source SHA, artifacts, version, historical results or production gates.

## What is implemented and what is not validated

`LocalModelEmbedder` already provided asset checksums, batching, lazy loading,
CLS/mean inference and content-addressed caches. This change reuses that
interface and adds family-specific DINOv2/BERT architecture validation,
explicit scientific image preprocessing and actual offline forward-pass tests.
It does not add another image reader or image analysis CLI. Decode TIFFs using
the existing image ingestion workflow; pass decoded pixels in NCHW order here.

The tests generate tiny random DINOv2 and BERT models using the installed
Transformers library and save local safetensors plus a local vocabulary. They
then load those weights through the real adapter and execute the real models.
Network connections are prohibited during those tests. These are software
tests, not pretrained model runs or biological validation. The original
mock-backend tests remain cache/interface checks.

No approved pretrained assets have been supplied. DINOv2/SapBERT catalog
entries still identify the proposed immutable checkpoints; they do not prove
license clearance, training-data independence or completed scientific runs.
Registry readiness and production dispatcher gates remain unchanged.

## DINOv2 input and inference

- Existing identifier: `facebook/dinov2-base`, revision
  `f9e44c814b77203eaa57a6bdbbd535f21ede1415`.
- Model: local `Dinov2Model`, 768 output dimensions, CLS token, L2 normalization.
- Input: finite numeric NCHW arrays, with every input channel named explicitly.
  Exactly three distinct channels must be selected in model-input order. There
  is no default RGB mapping, channel replication or filename/label interpretation.
- Scaling: supplied fixed input bounds to [0, 1]. Out-of-range/nonfinite values
  are errors; no per-image min/max fitting or clipping occurs.
- Resizing: direct resize to 224×224, antialiased bilinear interpolation,
  `align_corners=False`, no cropping. This can distort aspect ratio; this
  explicit software policy still requires scientific review for the dataset.
- Normalization: three supplied means/positive standard deviations, after
  resizing. No hidden image processor performs a second normalization.
- Preprocessing parameters are immutable tuples and part of fitted and cache
  identity. Changing them after fit requires refitting; no query statistics
  enter preprocessing.

Example for approved local assets and an explicitly reviewed channel policy:

```python
from perturb_lm.sklearn_api import ImagePreprocessing, LocalModelEmbedder, asset_catalog

# Illustrative technical settings only, not an approved Cell Painting mapping.
processing = ImagePreprocessing(
    input_channels=("c0", "c1", "c2", "c3", "c4"),
    model_channels=("c0", "c2", "c4"),
    input_range=(0.0, 65535.0),
    mean=(0.485, 0.456, 0.406),
    std=(0.229, 0.224, 0.225),
)
encoder = LocalModelEmbedder(
    asset_catalog()["dinov2"], asset_root=approved_local_asset_directory,
    image_preprocessing=processing, batch_size=8,
)
encoder.fit(reference_pixels)  # validates only; frozen checkpoint, no training
query_features = encoder.transform(separate_query_pixels)
```

Channel names are technical parameters, not biological labels or predictors.
Unselected channels do not enter embeddings; all channels must still pass QC.
Pixel-encoded acquisition effects and training-data overlap remain possible.

## SapBERT input and inference

- Existing identifier: `cambridgeltl/SapBERT-from-PubMedBERT-fulltext`, revision
  `090663c3ae57bf35ffe4d0d468a2a88d03051a4d`.
- Local BERT/tokenizer, nonempty strings, padding and truncation at 128 tokens.
- CLS from last hidden state, 768 dimensions, L2 normalization.
- Tokenizer, architecture, output dimension and positional capacity validated.
  Different row/batch order preserves corresponding feature rows.
- Use `LocalModelEmbedder(asset_catalog()["sapbert"], asset_root=approved_path)`.
  Text must pass the existing query-policy audit before benchmark use; this
  low-level encoder does not invent metadata or infer treatment identities.

Both loaders use local-only loading, disabled remote model code, safetensors,
eval mode and inference mode with gradients disabled. An approved checkpoint
must be supplied in safetensors format with a complete reviewed `asset.json`
covering all files. This implementation does not convert/download checkpoints
or authorize model use. Moving assets to another local path does not change
their decoded/model features; paths are provenance/cache identity only.

Pooling references: [DINOv2 documentation](https://huggingface.co/docs/transformers/model_doc/dinov2)
and [SapBERT model card](https://huggingface.co/cambridgeltl/SapBERT-from-PubMedBERT-fulltext).

## Verification and remaining work

`tests/test_offline_model_contracts.py` checks parameters and rejection without
Torch. `tests/test_offline_model_inference.py` requires the existing
`phase3c` extra and executes real random models, direct-output comparison,
channel ordering/sensitivity, padding/truncation, row order, caching,
cloning/pickling, immutable model weights and checksum/dimension rejection.
Linux source CI runs it without skipping or downloading weights.

Package CI validates this changed source independently; it does not rebuild
the unchanged #61 commit. PR runs upload only aggregate summaries. Candidate
archives require a separate manual workflow dispatch with explicit
`upload_candidate=true`; no release/registry upload is implemented.

Owners still need to record the software license decision in #32. Scientific
model use separately needs approved checkpoints/licenses, reviewed channel and
query contracts, overlap assessment and an approved comparison population.
No model matrix or Slurm job is submitted by this change.
