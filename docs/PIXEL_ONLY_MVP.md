# Pixel-only image-analysis baseline

This addition computes quantitative measurements from native numeric pixels.
It does not require gene names, treatment IDs, plate/well labels, batch labels,
text queries, a metadata dataframe, network access, or pretrained weights.
It does not change the historical Phase 3C benchmark or the production gates.

## Installed use

Install the `pixel` extra, then import:

```python
from perturb_lm.images.pixel_analyzer import PixelMorphologyTransformer

# Arrays: (N, C, H, W); alternatively a list of CHW arrays.
# Select the segmentation channel explicitly for the assay.
model = PixelMorphologyTransformer(segmentation_channel=0)
model.fit(training_images)  # scaling is fitted on training images only
features = model.transform(new_images)
labels = model.segment(new_images[0])
```

`fit` accepts an optional `y` for transformer compatibility, but ignores it.
No experimental metadata argument is accepted. Channel count/order and the
selected segmentation channel are technical input conventions, not biological
identity. Changing pixel calibration or channel order can change outputs.

## Implemented computations

- Otsu foreground thresholding and distance/watershed object separation.
- Object counts, areas, eccentricity, solidity, and perimeter.
- Per-channel raw intensity summaries, gradient energy, nonzero fractions.
- Train-only feature scaling; explicit feature names.
- A synthetic demo with a quantitative CSV, object-mask arrays, display overlay,
  and nearest training-image neighbors for held-out synthetic images.

```bash
python -m perturb_lm.images.pixel_demo --out /an/unused/demo/directory
```

The demo creates its own images. It never reads a biomedical dataset. It fits
feature scaling on images 0-7 and queries images 8-11. Neighbor distances are
exploratory, not an evaluated biological relevance metric. RGB conversion is
used only for the preview; quantitative calculations retain numeric channels.

## Limits

This is a CPU baseline, not a foundation model or validated cell analyzer.
Watershed objects are not automatically classified as nuclei or cells. A
suitable segmentation channel and reviewed parameters are needed for a real
assay. Measures are in pixels, not calibrated micrometers. Sparse signals,
low contrast, crowded objects, and illumination changes can impair results.
Validate actual-image masks against independent annotations before biological
claims. No claim is made that pixel-only inputs eliminate batch confounding:
acquisition artifacts can themselves be visible in pixels.

This module is tested with custom image fixtures and basic sklearn cloning and
Pipeline tests. It is not certified against every generic sklearn estimator
check; it accepts 4-D image batches rather than 2-D tabular feature matrices.

## Verification in the assistant container

24 focused tests passed. The synthetic demo also completed. Environment:
Python 3.13.5, NumPy 2.3.5, SciPy 1.17.0, scikit-learn 1.8.0,
scikit-image 0.26.0, tifffile 2026.5.15, Pillow 12.3.0, pytest 9.0.2.
This is not a run of the user's complete repository test suite or GitHub CI.
The patch has not been committed, pushed, merged, versioned, or published.

## Next research work

Add pinned image-encoder adapters and evaluate them separately from text
encoders. Add metadata-blindness and pixel-sensitivity tests, held-out acquisition
conditions, channel-dropout sensitivity, mask accuracy, and treatment-cluster
uncertainty. Ground-truth labels may be used by an external evaluator while
remaining absent from feature extraction.

## TIFF input

The core also exposes `read_tiff_chw(path, axes="CYX")`. Supported stored axes
are `YX`, `CYX`, and `YXC`. Set this from your image format, not by guessing.
Unknown axes and time/z volumes are rejected; there is no silent reshaping,
channel selection, resizing, or conversion to 8-bit. A list of returned CHW
arrays can be passed to the transformer. Raw-data processing should follow
your approved local data and code-review workflow; this helper does not enable
the gated production Benchmark V2 dispatcher.
