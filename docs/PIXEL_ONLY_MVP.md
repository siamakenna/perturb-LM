# Pixel-only image analysis

This installed-package workflow extends `PixelMorphologyTransformer` and the
existing `pixel_demo`. It requires no biological metadata table, model weights,
or network access. It does not enable Benchmark V2 production dispatch or alter
historical results.

## Install and commands

From the source checkout:

```bash
python -m pip install ".[pixel]"
perturb-lm images --help
```

The installed commands work outside the checkout. These examples assume two
channels stored in CYX order; provide your actual paths, axes, and channel order.

Analyze a single image without fitting anything:

```bash
perturb-lm images analyze image.tif \
  --axes CYX --channels c0,c1 --segmentation-channel 0 \
  --out outputs/image-analysis
```

Fit on designated reference images and persist an image index:

```bash
perturb-lm images fit reference-a.tif reference-b.tif \
  --axes CYX --channels c0,c1 --segmentation-channel 0 \
  --image-id ref-a --image-id ref-b --out outputs/image-reference
```

Apply that state to queries and search without refitting:

```bash
perturb-lm images search query.tif \
  --axes CYX --channels c0,c1 --image-id query-a \
  --reference outputs/image-reference --top-k 5 --out outputs/image-query
```

Export scaled query measurements without searching:

```bash
perturb-lm images analyze query.tif \
  --axes CYX --channels c0,c1 \
  --state outputs/image-reference/state.json --out outputs/scaled-query
```

Open each output's `report.html` locally. Output directories must be new.
Keep artifacts under ignored `outputs/` or outside the checkout. Reports retain
local source paths for traceability; review them before sharing.

## Input contract and QC

- Required `--axes`: `YX`, `CYX`, or `YXC`. YX has one channel. No
  time/Z flattening, cropping, channel inference, or quantitative resizing occurs.
  Multiple TIFF series require explicit `--series N`; this is not Z projection.
- Required `--channels`: unique channel names in decoded order. Queries must
  exactly match reference names/order. Names document the technical mapping and
  never enter feature computation. Incorrectly declared semantics cannot be detected.
- Fit/analyze expose `--segmentation-channel`, `--min-object-area`,
  `--smooth-sigma`, and `--min-peak-distance`. Saved-state analysis/search
  use reference settings. Channel 0 is never presumed to be DNA.
- Every input appears in `qc.csv`. Unreadable TIFFs, nonfinite/nonnumeric pixels,
  incompatible dimensions/channels, constant segmentation channels (`blank`),
  and no surviving foreground objects (`no_objects`) are excluded from features
  and the index. Invalid values are not replaced with valid-looking zeros.
- A constant unused channel is allowed when the chosen segmentation channel is
  usable. Finite low-quality/noisy images may still pass; inspect masks for the assay.
- Exit 0 means all accepted. Exit 1 means some excluded, with a completed report
  for accepted inputs. Exit 2 means all invalid or configuration/state failure.
  All-invalid batches produce QC/report files but no fitted state or index.

Use one `--image-id` per path or accept ordinal IDs such as `image_000000`.
IDs must be unique within a batch; duplicate pixels can remain distinct rows.
Paths and IDs are provenance only. No treatment identity is inferred from either.
Reference and query IDs occupy separate roles.

## Outputs and units

| Artifact | Contents |
| --- | --- |
| `raw_features.csv` | Raw image measurements keyed by image ID |
| `scaled_features.csv` | Reference z-scores; only after fit or with saved state |
| `measurements.csv` | Every object's image ID, mask label, shape and intensity measurements |
| `masks/*.tif` | Integer object IDs, background 0, matching measurement rows |
| `previews/*.png` | Display-only channels, boundary overlays and colored label masks |
| `qc.csv` | All input paths/IDs, acceptance and rejection details |
| `images.json` | Accepted row order, decoded-pixel hash, shape, dtype and path |
| `units.json` | Explicit feature/object units and channel order |
| `state.json` | Fitted preprocessing, parameters, schema and environment identity |
| `index.json` | Reference IDs/provenance, raw/scaled vectors, thumbnails and state binding |
| `neighbors.csv` | Query ID, rank, reference ID and Euclidean distance |
| `report.html` | Images, masks, QC, measurements and reference neighbors |
| `run.json`, `complete.json` | Counts/configuration and artifact checksums |

Areas are pixel²; perimeters and zero-based row/column centroids are pixels.
Eccentricity/solidity are dimensionless. Intensities retain decoded source units;
object intensity sums are source intensity summed over pixel count. Gradient
energy uses source-intensity²/pixel². Legacy feature names
`object_area_mean_px` and `object_area_std_px` remain, with pixel² in the
unit schema. Micrometer calibration is not implemented.

The report shows up to 100 object rows per image; CSV exports contain all objects.
Only previews are converted to contrast-scaled 8-bit. Quantitative calculations
use original numeric values. Raw-only analysis omits scaled features explicitly:
it never fits a scaler on query images.

## Reference state and retrieval

Only accepted reference images enter `StandardScaler.fit`. Query operations
load means, variances, scales, feature order, segmentation settings and channel
schema, without fitting or writing back to the reference files. Exact Euclidean
search uses the reference-scaled image features. Ties preserve reference row
order. Identical images can retrieve themselves; this exploratory workflow adds
no biological/acquisition exclusion rules.

State/index files are checksummed JSON, never pickle. Unknown schemas, invalid
scaler shapes/values, channel changes, mismatched indexes, corrupted checksums,
and extractor/dependency version changes fail before query analysis. Keep the
recorded environment; automatic migration is not supported. Checksums detect
accidental corruption, not maliciously rewritten artifacts.

Output bundles are built in temporary sibling directories and published after
checksums are written. Existing output is not overwritten. Interrupted processes
can leave hidden temporary directories, which should not be used as completed runs.

## Python and demo

```python
from perturb_lm.images.pixel_analyzer import PixelMorphologyTransformer, read_tiff_chw
from perturb_lm.images.pixel_state import load_preprocessor
from perturb_lm.images.pixel_workflow import run_images

image = read_tiff_chw("image.tif", axes="CYX")
raw, mask, objects = PixelMorphologyTransformer(segmentation_channel=0).measure(image)
model, state = load_preprocessor("outputs/image-reference/state.json",
                                channels=["c0", "c1"])
scaled = model.transform([image])
run_images(["image.tif"], output="outputs/python-analysis",
           axes="CYX", channels=["c0", "c1"])
```

Array inputs are NCHW or a list of CHW arrays. `fit(X, y)` ignores `y`.
Blank segmentation channels now fail explicitly. The existing synthetic demo
shares the same extractor and overlay renderer:

```bash
python -m perturb_lm.images.pixel_demo --out outputs/pixel-demo
```

## Verification and limits

```bash
python -m pip install -e ".[pixel,dev]"
python -m pytest -q tests/test_pixel_analyzer.py tests/test_pixel_workflow.py tests/test_pixel_installed.py
python -m pytest -q
```

The installed test builds a wheel without downloading dependencies, installs it
non-editably into a temporary environment, verifies its import location, and runs
the actual console script outside the checkout. It covers all commands, state
reuse, and the original demo. CI installs the pixel extra and uses generated
synthetic TIFFs only.

This is a CPU, in-memory 2-D watershed baseline for moderate collections, not a
validated cell/nucleus classifier or scalable image database. Fit retains reference
images in memory; index/report retain all feature rows. No 3-D segmentation,
physical calibration, batch correction, channel harmonization, or automatic mask
accuracy assessment is implemented. Acquisition artifacts can affect pixel
features. Neighbors are exploratory similarity, not biological relevance evidence.
