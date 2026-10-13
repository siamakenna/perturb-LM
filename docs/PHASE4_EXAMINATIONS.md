# Phase 4 examination and comparator follow-up

This change is separate from alpha package readiness. It adds a versioned
readiness inventory and bounded execution only for implemented synthetic
examinations. It neither submits jobs nor authorizes model/data access.
Related work: #55, image PR #59, acceptance PR #60, release PR #61.

## Existing adapters before new work

The existing `LocalModelEmbedder` validates local asset identity and checksums,
loads Hugging Face models with `local_files_only=True` and
`trust_remote_code=False`, extracts actual model features, validates output
dimensions, and applies declared L2 normalization. DINOv2 and SapBERT already
have catalog specs and share these implemented image/text inference paths.
Do not replace those with additional registry-only adapters. Current synthetic
tests mock the backend boundary; they are not pretrained checkpoint evidence.

No approved local checkpoints were supplied for this session. Next adapter
work must first review the pinned asset manifests, licenses and training-data
overlap. No checkpoint downloads or executable model-code approvals are implied.
Priority remains DINOv2 image features, then SapBERT text features.

| Family | Current repository readiness |
| --- | --- |
| BiomedBERT | Existing text encoder and offline generic adapter |
| MedCPT | Existing text comparator and offline generic adapter |
| BioLORD | Existing text comparator and offline generic adapter |
| CellCLIP | Historical comparator work; generic image backend remains review-gated |
| DINOv2 | Actual generic HF image loader; scientific channel/preprocessing contract needs review |
| OpenPhenom | Pinned inventory; specialized backend remains disabled |
| Microsnoop | Candidate; code, license, assets and overlap review required |
| SapBERT | Actual generic HF text loader; approved checkpoint validation pending |
| SciBERT | Candidate; code, license, assets and overlap review required |
| BlueBERT | Candidate; code, license, assets and overlap review required |

PR #49's comparator head is the same code merged via PR #50; do not recreate
it. Pooling variants do not increase the family count. The ten-family inventory
is a target, not ten implemented/validated model families.

For DINOv2 the current catalog pins `facebook/dinov2-base` revision
`f9e44c814b77203eaa57a6bdbbd535f21ede1415`, expects N×3×224×224 input,
uses the local image processor configuration, extracts the CLS token (768
dimensions), then L2 normalizes. Those shape checks alone do not define a
scientifically justified channel mapping. Before real comparison, record the
three explicitly selected scientific channels, input numeric range, clipping,
resizing, interpolation, rescaling/normalization flags and processor checksums.
Reject unmapped multichannel input. Never use a display RGB thumbnail as a
silent feature input.

SapBERT's existing spec pins
`cambridgeltl/SapBERT-from-PubMedBERT-fulltext` revision
`090663c3ae57bf35ffe4d0d468a2a88d03051a4d`, CLS pooling, 768 dimensions,
128-token truncation and L2 normalization. Reuse the local tokenizer/model
loader and reviewed query-policy audit. Both specs remain subject to asset
review; a catalog entry is not executed model validation.

Keep metadata search, text-to-morphology retrieval and image-only retrieval as
separate tracks. Lexical/random/shuffled controls, handcrafted pixel features
and CellProfiler profiles stay visible as distinct controls.

## Paired statistics

`QueryBootstrap` is extended rather than replaced. Defaults preserve paired
query resampling and query-weighted estimates. Query IDs define pairing;
when treatments are supplied, complete exact membership must match by query
ID. Supply dataset-qualified treatment IDs when needed; membership is never
inferred from paths.

`resampling_unit="treatment_cluster"` resamples whole treatments and requires
at least two evaluable treatments. `estimand="query_weighted"` weights each
selected query equally; `estimand="equal_treatment"` averages treatment means
equally. With query resampling, equal-treatment estimation resamples queries
within every treatment so the treatment set stays fixed. The output explicitly
identifies these settings and reports total/evaluable/excluded query counts
and treatment counts. Undefined paired AP is excluded, not changed to zero.
Evaluator per-query tables retain explicit exclusions.

These intervals quantify fixed-prediction uncertainty conditional on the
retained population. They do not include split/training variation. Repeated
split/retraining examination needs a separate reviewed design; seeds and jobs
are not acquisition batches. Cluster intervals with few treatments can be weak.

## Versioned examination manifest and runner

`configs/phase4_examinations_v1.json` lists all ten requested examinations.
Only installed-wheel independence, metadata blindness, filename independence,
controlled pixel sensitivity and bootstrap software checks are runnable now.
The other five require reviewed protocols/data/assets and cannot be selected.
Segmentation accuracy requires independent annotations, not masks generated
by the same segmenter. Synthetic size checks are not segmentation validation.

`scripts/run_phase4_examinations.py` runs one allowlisted existing test group,
records source/runner/manifest hashes and exact counts/exit status, and rejects
skips or source mutation. It reuses timeout/process-group handling from the
acceptance runner. Private logs/XML remain local; inspect only the aggregate
summary before sharing. Groups overlap and are never summed.

After review, for an ordinary local synthetic check:

```bash
python scripts/run_phase4_examinations.py --repo /path/to/clean/checkout \
  --out /path/to/new/private-output --examination statistical_stability
```

`slurm/phase4_examinations.sbatch` is a dedicated single-examination wrapper:
2 CPUs, 8 GB, 35 minutes, no GPU and no array. It accepts EXAM_REPO, EXAM_ENV,
EXAM_OUT and EXAM_NAME. No jobs or matrix were submitted. The old embedding
smoke runner is not repurposed. This wrapper does not create ten batches.
