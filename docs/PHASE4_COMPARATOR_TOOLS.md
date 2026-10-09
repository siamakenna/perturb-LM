# Phase 4 comparator operator tools

These version 1.0.2 tools prepare existing inputs and inspect existing feature
exports. The launcher delegates inference to the existing native pilot worker.
They add no encoder, downloader, evaluator, alignment trainer, or approvals.
See [the pilot contract](PHASE4_PRETRAINED_PILOTS.md) for the reviewed manifest,
asset, input, and completion requirements. Synthetic checks establish software
behavior only; no pretrained result is established by this integration.

## Files and execution environment

- `scripts/comparator_tools.py`: image inventory preparation, NPZ inspection,
  descriptive feature geometry, and summaries of existing per-query scores.
- `scripts/prepare_native_launch.py`: private request validation and native
  inspection; never submits a job.
- `slurm/run_dinov2_once.sbatch`: bounded CPU wrapper around the unchanged
  `slurm/phase4_pilot.sbatch` and native worker.
- `configs/pilots/operator_templates/`: incomplete templates to copy into
  private storage and fill using actual selection records and reviewed settings.

Use the existing project environment. NumPy supports feature analysis; TIFF
preparation also requires tifffile. Native preparation checks the installed
torch, transformers, NumPy, and tifffile versions and the imported worker path.
It neither installs nor upgrades packages. On Biowulf, perform tests, TIFF
decoding, native preparation, and numerical analysis inside an appropriate
compute allocation. The wrapper retains the existing Python 3.11 module setup.

Keep requests, approvals, input files, models, row-level outputs, and launch
environments outside the source checkout on approved private storage. All new
output directories must have an existing parent and must not already exist.

## Input preparation

Select one to eight already staged TIFFs. Selection rows contain exactly
`record_id` and `path`, with paths relative to the chosen data root. IDs are
unique strings; missing-value names `nan`, `none`, `null`, and `<na>` are rejected
case-insensitively. Input order is preserved.

Declare `CYX` or `YXC`, three to eight named input channels, three distinct
ordered model channels, fixed input range, and finite normalization mean/std
with positive std. Both spatial dimensions must be between 8 and 1024 inclusive;
images must have uniform shapes and each file must be at most 32 MiB. The tool
checks numeric pixels, range, path confinement, and stable checksums. It does
not choose stain meanings, assemble channels, resize, or alter image pixels.

From the repository root, after setting these variables to actual private paths:

```bash
(
  set -eu
  : "${PILOT_PYTHON:?Set the existing environment's absolute bin/python path}"
  : "${IMAGE_SELECTION:?Set the completed selection JSON path}"
  : "${IMAGE_DATA_ROOT:?Set the image root}"
  : "${IMAGE_SETTINGS:?Set the reviewed settings JSON path}"
  : "${IMAGE_PREPARATION_OUT:?Set a fresh private output directory}"
  "$PILOT_PYTHON" scripts/comparator_tools.py prepare-images \
    --selection "$IMAGE_SELECTION" --data-root "$IMAGE_DATA_ROOT" \
    --settings "$IMAGE_SETTINGS" --out "$IMAGE_PREPARATION_OUT"
)
```

Outputs include `image-inventory.json`, validated `image-settings.json`, private
image QC, and a summary. Place the inventory under the data root at the relative
location named by the reviewed manifest's `dataset.metadata_path`; bind its
exact byte SHA-256 in `dataset.metadata_sha256`. The manifest's `image` settings
must agree with those checked. Native inspection reports the canonical pilot
hash used for approvals; that hash is not the raw manifest-file hash.

## Native launch preparation

Use a genuine, clean Git checkout at the reviewed source commit. Applying a
patch leaves that checkout dirty until the contribution is committed and
reviewed. A new reviewed commit requires an approval bound to that commit;
do not reuse an old source-commit attestation. A source-only ZIP supports
inspection and tests but cannot satisfy the launcher's Git identity checks.

Prepare only with an existing `approved_inference` DINOv2 manifest, genuine
approval records, and staged assets with the native `asset.json`. The checked-in
`plan_only` proposal deliberately cannot launch. Record existing absolute paths
interactively, entering one path at each prompt:

```bash
(
  set -eu
  : "${PILOT_PYTHON:?Set the existing environment's absolute bin/python path}"
  : "${PILOT_REQUEST:?Set a new private request JSON path}"
  "$PILOT_PYTHON" scripts/prepare_native_launch.py make-request \
    --out "$PILOT_REQUEST"
)
```

The request contains `manifest`, `approval`, `data_root`, `asset_root`, and
`pilot_output`. The approval file must resolve inside `data_root`. Preparation
keeps its absolute path in the checksum bindings but exports `PILOT_APPROVAL`
relative to that root, matching the native CLI. The outer wrapper changes to
the data root before the native wrapper checks the approval file. The native
worker and native wrapper remain unchanged.

```bash
(
  set -eu
  : "${PILOT_PYTHON:?Set the existing environment's absolute bin/python path}"
  : "${PILOT_REQUEST:?Set the completed private request JSON path}"
  : "${PILOT_CODE:?Set the genuine clean reviewed checkout}"
  : "${PILOT_REVIEWED_SHA:?Set its full reviewed commit SHA}"
  : "${PILOT_PREPARATION_OUT:?Set a fresh private preparation directory}"
  "$PILOT_PYTHON" scripts/prepare_native_launch.py prepare \
    --request "$PILOT_REQUEST" --code "$PILOT_CODE" \
    --python "$PILOT_PYTHON" --source-sha "$PILOT_REVIEWED_SHA" \
    --out "$PILOT_PREPARATION_OUT"
)
```

Preparation writes private file bindings, `launch.env.sh`, inspection logs, and
`preparation-summary.json`. The preparation directory must differ from the
planned pilot output. Both the final pilot output and its sibling `.working`
path must be absent. Any bound input change requires new preparation.

Preparation is not full approval or asset validation. Those checks remain in
the native worker, and the operator must verify the linked decisions. After
separate authorization for one run, the outer wrapper accepts the generated
environment file as its first argument and the literal
`I_AUTHORIZE_ONE_DINOV2_PILOT` as its second. It requires a Slurm allocation,
rejects arrays, rechecks source and bound files, and delegates to the native
worker. Its request remains two CPUs, zero GPUs, 8 GiB, ten minutes, and at
most eight images. Nothing in input preparation or testing submits that job.

## Existing embedding and score analysis

Native `embeddings.npz` uses `embeddings` and `record_ids`; automatic key
selection supports this schema. For a completed DINOv2 pilot with at least two
records, run from the repository root:

```bash
(
  set -eu
  : "${PILOT_PYTHON:?Set the existing environment's absolute bin/python path}"
  : "${EMBEDDINGS_NPZ:?Set the existing native embeddings.npz path}"
  : "${ANALYSIS_OUT:?Set a fresh private analysis output directory}"
  "$PILOT_PYTHON" scripts/comparator_tools.py analyze \
    --npz "$EMBEDDINGS_NPZ" --expected-dim 768 \
    --require-float32 --require-unit --out "$ANALYSIS_OUT"
)
```

The native pilot accepts one image, but descriptive pairwise analysis requires
2–2048 records. Analysis rejects object arrays, nonfinite or zero-length vectors,
and integer values outside the exact float64 integer range. It checks declared
feature properties and excludes self-neighbors. It does not validate native
completion provenance; review `complete.json` and its output checksums first.
The analysis tool's `analysis-complete.json` is a separate completion marker.

Use `compare --help` to compare representations with exactly matching record-ID
sets and an explicit image/well/treatment/record unit. ID order is aligned by
explicit keys. Pairwise cosine rank correlation and neighbor overlap describe
geometry; they are not cross-modal retrieval scores. Comparability of input
populations and aggregation units remains a scientific decision.

Use `scores-summary --help` to summarize existing evaluator exports. It rejects
duplicate headers, malformed rows, inconsistent query coverage, and duplicate
method/query pairs. It reports conditional means and evaluability counts; it
does not construct relevance, apply leakage exclusions, or bootstrap uncertainty.
Keep `M0_GENE_AWARE_V1` and `M0_IDENTITY_FREE_V2` in separate analyses. A condition
label records the operator's assertion, not independent verification of a query
policy. Use the existing evaluator for scientific comparisons and retain the
nonevaluable-query counts.

## Validation

With the repository's development and pixel dependencies installed, run:

```bash
python -m pytest -q -p no:cacheprovider tests/test_phase4_comparator_tools.py \
  tests/test_phase4_comparator_regressions.py tests/test_phase4_launch_regressions.py \
  tests/test_phase4_input_contract.py tests/test_phase4_native_contract.py
```

The focused unittest modules can also run without pytest or model dependencies:

```bash
python -m unittest discover -s tests -p 'test_phase4_*regressions.py'
python -m unittest discover -s tests -p 'test_phase4_input_contract.py'
python -m unittest discover -s tests -p 'test_phase4_native_contract.py'
```

Native contract checks use actual source inspection and embedding serialization,
plus isolated synthetic fixtures for rejection paths and argument forwarding.
TIFF schema checks that mock decoding do not establish actual TIFF I/O. These
tests do not run pretrained inference or establish scientific performance.

## Integration review, 2026-10-09

The integration was independently fetched from GitHub at
`c515807ca5108cf6bc0f5d77bb7c446dd9783e11`, based on
`a6a385b2dd8389ef61c70111c76612c9e95164e4`. Review is tracked in
[PR #71](https://github.com/siamakenna/perturb-LM/pull/71), referencing
[issue #55](https://github.com/siamakenna/perturb-LM/issues/55).
Commit `e8bfeba1c1dc4e4d3a4c422039b36225a8095379` fixes the capture-only
test interpreter for Python executable paths containing spaces and applies
the repository's lint conventions to the new Python files. The native worker,
model adapters, evaluator, and historical results are unchanged.

Local macOS Intel / Python 3.12.5 validation of that follow-up:

- The five-file command above: **91 passed, 30 subtests passed**, no failures
  or skips. This reproduces the focused count reported by the operator on
  Biowulf for the original integration; it is not a full repository suite.
- `python -m pytest --continue-on-collection-errors -q`: **464 passed,
  3 collection errors, 30 subtests passed**, exit 1. No tests were excluded.
  The errors are missing Torch imports in `test_comparator_text_encoders.py`,
  `test_offline_model_inference.py`, and `test_pilot_inference.py`.
  This is incomplete local dependency coverage, not a passing full suite.
- Ruff on the seven new Python files, Bash syntax on the bounded wrapper,
  public-copy consistency, and Git whitespace checks passed.
- Actual native DINOv2 inspection returned `execution=plan_only`, with
  `approval_verified`, `assets_verified`, and `inputs_verified` all false.

The test groups overlap; do not add their counts. Dependency-enabled Linux
source checks and artifact-install checks are tracked on the PR's current
revision. The previously validated package is still **BUILT_NOT_RELEASED**;
this integration does not establish a publication or a new pretrained result.

Before a real pilot, the operator still needs an approved TIFF selection of
at most eight images, explicit reviewed channel/preprocessing settings,
the pinned local checkpoint inventory, and recorded decisions bound to the
final reviewed source commit, manifest, and assets. Inspection found no TIFFs
or native asset inventories in the local project data/output directories
checked for this review; it does not establish their absence elsewhere.
No new Biowulf rerun of the unchanged package candidate is required by these
operator-tool changes. Any future pretrained pilot is separate work requiring
those prerequisites and explicit run authorization.
