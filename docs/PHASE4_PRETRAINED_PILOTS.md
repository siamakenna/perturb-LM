# Proposed first pretrained pilots — approval pending

Related to #55, following #63. These are at most eight-row frozen-feature
inference pilots, not a benchmark matrix, alignment experiment, paper result,
or authorization to acquire assets. Software distribution approval in #32 is
separate from third-party model/data/scientific-use decisions.

## Reused components and implementation boundary

`python -m perturb_lm.sklearn_api.pilot` reuses `AssetSpec`,
`DatasetManifest`, `Resources`, `LocalModelEmbedder`,
`ImagePreprocessing`, `QueryPolicyTransformer`, `code_identity` and
`save_embedding_stage`. It has no scheduler, downloader, retrieval evaluator
or alignment trainer. The existing Benchmark V2 dispatcher is unchanged and
still rejects production execution; M1/M5 and plan_only restrictions remain.

The two JSON proposals under `configs/pilots/` use `execution: plan_only`.
Input-inventory hashes, approved dataset version and DINOv2 channel settings
are explicitly unresolved. Inspect works; run rejects them before loading data
or assets. Editing execution alone cannot authorize inference.

## Checkpoints, files and asset-use review

| Pilot | Proposed immutable identifier/revision | Minimum reviewed local files |
| --- | --- | --- |
| DINOv2 | `facebook/dinov2-base` / `f9e44c814b77203eaa57a6bdbbd535f21ede1415` | config.json, model.safetensors; retain README/license notices and preprocessor_config.json for review |
| SapBERT | `cambridgeltl/SapBERT-from-PubMedBERT-fulltext` / `090663c3ae57bf35ffe4d0d468a2a88d03051a4d` | config.json, model.safetensors, vocab.txt, tokenizer_config.json, special_tokens_map.json; retain README/license notices |

SapBERT's tokenizer uses the same identifier and revision as its checkpoint.
DINOv2 has no tokenizer. The pinned Hugging Face metadata endpoints were read
without downloading weights; both revisions exist, list safetensors, and
advertise Apache-2.0. Sources:
[DINOv2 revision metadata](https://huggingface.co/api/models/facebook/dinov2-base/revision/f9e44c814b77203eaa57a6bdbbd535f21ede1415),
[SapBERT revision metadata](https://huggingface.co/api/models/cambridgeltl/SapBERT-from-PubMedBERT-fulltext/revision/090663c3ae57bf35ffe4d0d468a2a88d03051a4d).

That metadata is a proposed license basis, not completed usage clearance.
Responsible reviewers must check the pinned terms, notices, inherited assets,
training-data overlap and intended use, then record the decision in a
repository issue/PR comment. No project asset-use approval reference exists yet.
Every local file checksum is **pending approved staging**. Do not fabricate
weight hashes. The existing `asset.json` must name the exact identifier and
revision, set complete=true and SHA-256-cover every staged file except itself.
The pilot binds the SHA-256 of that manifest and rechecks all assets after
inference. No download, conversion, random fallback or remote model code occurs.

## Input and feature contracts

DINOv2's role is an image-only learned representation beside handcrafted
pixel/CellProfiler controls. Its native convention is three-channel natural
images; selecting microscopy channels is an adaptation requiring review.
The image inventory is a JSON list of only `record_id`, relative `path`
and `sha256`. Its own SHA-256 occupies DatasetManifest.metadata_sha256.
There is no biological metadata table in this path. Every TIFF uses explicitly
declared CYX or YXC axes and the existing reader. Uniform image dimensions are
required; bounds are eight channels, 1024×1024 and 32 MiB per input file.
Large compressed images still need staging review; Slurm enforces the memory
ceiling if decoding exceeds assumptions.

Before approval fill `image` with `axes` and `preprocessing`:
named `input_channels`, exactly three distinct ordered `model_channels`,
`input_range`, three `mean` and positive `std` values. No default mapping
is supplied. Fixed range maps pixels to [0,1]; out-of-range/nonfinite input
fails. Direct antialiased bilinear resize to 224×224 uses align_corners=False,
no crop, clipping, display RGB conversion or per-image scaling. Normalization
then uses the approved means/stds. CLS pooling yields 768 L2-normalized values.
Technical channel names are not predictive biological labels.

SapBERT's role is frozen text features, not text-to-image retrieval by itself.
The only first-pilot query condition is **M0_IDENTITY_FREE_V2, version 2**.
A checksummed CSV supplies explicit record_id and the allowed perturbation/
control-type fields. Treatment, gene, plate and other identifiers can be
provided solely to the existing leakage audit; they are not encoder inputs.
The audit's universe is the supplied inventory, not an externally inferred
ontology. Input approval must establish that this universe and the allowed
fields are appropriate. Tokenization pads/truncates to 128 tokens; CLS pooling
yields 768 L2-normalized values. No alignment is involved and no fitting
partition is consumed; future alignment needs a separate training-only plan.
Historical M0_GENE_AWARE_V1 results are not relabeled.

Both outputs are finite float32, shape N×768 for the proposed checkpoints,
with exactly the input record_id order. Rows are never sorted or inferred from
filenames. Input and asset changes, duplicate IDs, incompatible dimensions,
bad checksums, missing weights and missing approvals fail without a completion
marker. Failures do not substitute zeros, random embeddings or random weights.

## Approval document and completion evidence

After owners record all three decisions, create a private JSON approval file:

```json
{
  "schema_version": 1,
  "pilot_sha256": null,
  "source_commit": null,
  "asset_manifest_sha256": null,
  "decisions": {
    "asset_use": {"status": "pending", "reviewer": null, "reference": null},
    "input_use": {"status": "pending", "reviewer": null, "reference": null},
    "scientific_protocol": {"status": "pending", "reviewer": null, "reference": null}
  }
}
```

The worker rejects this template. Each approved decision must cite a specific
repository issue/PR comment or review, with a recognized project reviewer;
scientific_protocol requires the responsible owner, siamakenna. The exact
source commit, canonical pilot hash and asset-manifest hash must match.
This is an offline attestation contract, not cryptographic authentication:
operators must independently verify the linked decisions and restrict access
to the approval file. The worker does not manufacture or remotely verify reviews.

A completed run writes private embeddings.npz with row IDs and complete.json
through the existing atomic writer. Provenance records source/code hashes,
pilot/input/asset/approval hashes, row-order hash, full model/preprocessing/
query contracts, dependency versions and source_unchanged. Completion requires
bounded rows, correct shape/dtype/unit norms, no input/asset/source mutation
and valid output checksums. Keep these row-level files private; no upload is
part of this worker. A successful pilot establishes inference plumbing only.

## Implemented commands and machine boundaries

**Mac / ordinary development checkout:** inspect only, requiring no model assets:

```bash
python -m perturb_lm.sklearn_api.pilot inspect --manifest configs/pilots/dinov2_v1.json
python -m perturb_lm.sklearn_api.pilot inspect --manifest configs/pilots/sapbert_v1.json
```

**Biowulf login, only after approvals and separate permission to run:** select
the reviewed source revision and preinstalled `.[phase3c,pixel]` environment.
Set PILOT_CODE, PILOT_ENV, PILOT_MANIFEST, PILOT_APPROVAL, PILOT_DATA,
PILOT_ASSETS and a fresh PILOT_OUT **on Biowulf**. No Mac shell values transfer.
Paths and the approved revision are unresolved; this document provides no
pre-filled submission command. Empty/missing values and checked-in proposals
cannot launch inference. Environment installation/assets staging requires its
own authorization and approved compute allocation.

**Compute node, in a separately approved allocation:** the dedicated
`slurm/phase4_pilot.sbatch` implements one CPU job, 2 CPUs, 8 GiB and 10 minutes,
not an array or ten batches. It invokes this tested command after checking
required variables/files:

```bash
"$PILOT_ENV/bin/python" -m perturb_lm.sklearn_api.pilot run \
  --manifest "$PILOT_MANIFEST" --approval "$PILOT_APPROVAL" \
  --data-root "$PILOT_DATA" --asset-root "$PILOT_ASSETS" --out "$PILOT_OUT"
```

No job was submitted and no pretrained checkpoint ran. The worker and CLI are
tested with locally generated tiny random checkpoints under explicit synthetic
mode, which requires synthetic dataset/asset declarations and cannot use a
pretrained override in approved_inference mode.

## Remaining examinations

#62 already implements keyed query pairing, treatment membership validation,
query and whole-treatment resampling, query-weighted/equal-treatment estimates,
and explicit nonevaluable-query counts for fixed predictions. Its bounded
runner executes five synthetic software groups. Retrieval workers export keyed
per-query scores and exclusions through the existing aggregation path.
Channel-selection tests in #63 are software checks, not a completed scientific
channel-ablation study. Independent segmentation, nuisance robustness, acquisition/
biological generalization, learned-versus-handcrafted comparisons and split/
retraining variation still require reviewed designs/data/assets.

BiomedBERT, MedCPT, BioLORD, CellCLIP, DINOv2, SapBERT, SciBERT, BlueBERT,
OpenPhenom and Microsnoop remain a ten-family target. Existing lexical and
handcrafted controls remain separate. No new model scores or paper claims are
created by these pilots.
