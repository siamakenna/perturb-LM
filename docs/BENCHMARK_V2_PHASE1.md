# Benchmark V2: Phase 1 foundation

Status: locally tested infrastructure and synthetic checks only. No new scientific
results, model weights, dataset downloads, paper changes, or Biowulf runs. Work is
scoped to the user-requested Phase 1 on `feature/benchmark-v2-scikit`; no issue
number was supplied. Scientific benchmark changes require a reviewed experiment
issue before real execution.

## Frozen CPJUMP1 boundary

The scientific reference remains [Phase 3B Foundation Readiness](PHASE3B_FOUNDATION_READINESS.md),
including its full-query selection, published metrics and query-bootstrap intervals.
Do not interpret its historical “identifier-stripped” name as gene-free: its
allowed fields include `Metadata_gene`.

Existing evaluation entry points are `scripts/run_jump_text_profile_retrieval.py`
and `perturb_lm.retrieval.text_profile.run_text_profile_retrieval[_multi_seed]`.
They build treatment-level queries, score profile rows, use sklearn score-based
average precision, and report Hit/Recall at 1, 5 and 10 with evaluable-query counts.
Their TF-IDF fits the combined query/candidate corpus. The later Phase 3C entry
point is `scripts/run_phase3c_alignment.py`; it is a distinct train/test workflow.
Neither implementation is modified or routed through V2.

`tests/fixtures/benchmark_v2/frozen_reference.json` records source/document hashes
and paths/checksums of the existing local aggregate and bootstrap CSVs under
`outputs/phase3b_corrected_baseline_full_original/`. It contains no copied metric
tables. Regression checks verify these files when present, and explicitly mark
local result files unavailable on clean installations. Existing synthetic
regression tests continue to exercise the original evaluator.

The reference commit `ccec3b94ea6b5061a2d221c553b15e1fb1a93cc1` was subsequently
fetched and inspected in Turn 2. The implementation base remains
`56ec4d08d2b638d0d1d8b8f559ab32e8f0cc15d0`; they are not equivalent.
See [the reconciliation](BENCHMARK_V2_PROVENANCE_RECONCILIATION.md).

The CPJUMP1 regression configuration performs **read-only artifact verification**,
never a benchmark rerun. Its model entries describe provenance placeholders, not
executed models; `unaligned_cosine` is explicitly marked as not executed.
The unfiltered split describes the frozen lexical reference. Bootstrap settings
in that configuration are inert. The stored reference files remain authoritative.

## Public API and boundaries

Import from `perturb_lm.sklearn_api`:

| Component | Contract |
| --- | --- |
| `DatasetManifest`, `ManifestDatasetAdapter` | Versioned, checksummed local metadata; `load()` rather than an artificial estimator `fit()` |
| `CPJUMP1MetadataAdapter` | Normalize existing local profile metadata; no feature downloads or result recomputation |
| `QueryPolicyTransformer` | `fit` records an identifier audit universe; `transform` renders and audits query records |
| `TfidfTextEmbedder` | Train-only word or character vocabulary, standard `fit/transform` |
| `MorphologyEmbedder` | Train-only numeric scaling of precomputed features/embeddings |
| `AlignmentEstimator` | Paired `fit(text, morphology)`, `transform/predict(text)` in morphology coordinates |
| `RetrievalEstimator` | `fit(gallery)`, `predict(queries)` returns a full score matrix |
| `MetricEvaluator`, `QueryBootstrap` | Stateless `evaluate`; parameter inspection/cloning without pretending to learn parameters |
| `BenchmarkPipeline` | Explicit training metadata/morphology plus held-out gallery; `predict`, `evaluate`, `score` |

All estimators support sklearn cloning and nested `get_params/set_params`. Dataset
adapters, immutable configuration records, and execution planning remain outside
sklearn estimator semantics. The multimodal pipeline uses explicit keyword-only
gallery inputs instead of forcing them through sklearn's single-matrix Pipeline.
It is not advertised as directly compatible with generic `cross_val_score`.

Example with already loaded, aligned numeric matrices:

```python
from perturb_lm.sklearn_api import BenchmarkPipeline, SplitSpec

benchmark = BenchmarkPipeline(split=SplitSpec("held_out_plate"), synthetic=True)
benchmark.fit(train_metadata, train_morphology,
              gallery=test_metadata, gallery_y=test_morphology)
result = benchmark.evaluate(test_metadata)
# result.summary, result.per_query, result.exclusions
```

Only training rows fit vocabularies, scalers and projection parameters. The
identifier audit may inspect all supplied metadata because it learns no numeric
representation. Callers must preserve metadata/matrix row alignment. Each matrix
row corresponds to its metadata row in positional order.

Ridge, PLS and CCA are implemented; PLS/CCA use regression predictions in the
morphology feature space, not their modality-specific latent coordinates.
Turn 2 also adds synthetic-tested NumPy MLP and contrastive projection heads.
Unaligned cosine requires matching dimensions and never inserts a random
projection. Random ranking, query shuffling and exact-gene lookup are explicit
controls; exact-gene lookup runs outside the morphology pipeline. Query shuffling
is not the frozen evaluator's shuffled-label control.

## Query contracts

Every query includes a stable ID derived from dataset/record/policy/version,
allowed source fields, rendered text, separate biological identity, provenance,
and a structured audit. These are record-level V2 query IDs, not a replacement
for the frozen treatment-level IDs. Audit failures raise before encoding.

| Policy | Rendering contract |
| --- | --- |
| `M0_GENE_AWARE_V1` / 1 | Historical gene-aware phrasing, with perturbation type fallback; allowed source list matches the historical four fields |
| `M0_IDENTITY_FREE_V2` / 2 | Perturbation/control types only; genes, aliases, treatment, compound, sequence and acquisition identifiers prohibited |
| `M1_BIOLOGICAL_CONTEXT` / 1-draft | Supplied `biological_context` plus required `annotation_provenance`; identifiers prohibited |
| `M5_LEAKAGE_CONTROL` / 1-draft | Constant neutral text `cellular perturbation`; identifiers prohibited |

The user explicitly approved **provisional synthetic-only** M1/M5 contracts for
Phase 1. They do not define approved real-data experiments. Non-synthetic pipeline
execution rejects provisional policies; expanded configurations only plan them.

Audits apply Unicode normalization and case-insensitive token boundaries against
the entire supplied identifier universe, including short identifiers and supplied
alias lists. They do not query external ontologies, infer unprovided aliases, or
certify that all possible biological identity clues have been removed. Supply the
complete identifier universe at fit time; review annotation sources before real use.

## Data, splits and evaluation

The manifest declares dataset/version, relative metadata and optional representation
paths/checksums, public/restricted access, precomputed/computed representations,
synthetic status, and well/treatment retrieval unit. Paths resolve beneath an
explicit local root; restricted loading requires an explicit opt-in. A manifest is
not a download specification. Computed image representations are an extension
point, not implemented inference.

Normalized records distinguish dataset, batch, source, plate, well, treatment,
perturbation, gene, compound, replicate, image/profile IDs and split membership.
Missing metadata remains explicit. The CPJUMP1 adapter retains original columns,
uses `Metadata_Inferred_Batch` as a fallback, and leaves unavailable source and
replicate identities blank rather than inventing them. Such rows need reviewed
metadata enrichment before source-sensitive evaluation.

The schema recognizes CPJUMP1, JUMP cpg0016/cpg0000/cpg0002, RxRx1, RxRx19a and
PERISCOPE. Turn 2 adds configurable local JUMP/RxRx mappings to the normalized
metadata and lightweight CPJUMP1 adapters. These are synthetic schema checks;
each real dataset still requires a reviewed mapping and checksummed local assets.

`SplitSpec.validate(train, test)` checks held-out plate, treatment, batch, source,
or dataset identity. It rejects missing split keys and shared records. Plate
identity is scoped by dataset/source/batch; treatment identity is conservatively
global and must be harmonized for transfer experiments. It validates explicit
membership, rather than silently generating a random split.

Candidate filters independently exclude the same physical plate, the same well
coordinate **across plates**, treatment, batch, source, or record. Missing filter
metadata fails closed and yields machine-readable reasons. Missing query treatment
and no positives after filtering are query exclusions. Treatment filtering can
remove every exact-label positive; this is reported as non-evaluable, not zero AP.

Well retrieval requires one row per physical well. Missing well keys are excluded;
duplicate well rows require explicit upstream aggregation. Treatment retrieval
filters rows first and then takes the mean score of remaining rows per treatment.
Future image/site aggregation and alternate relevance definitions need review.

V2 AP uses score-threshold ties via sklearn. Hit/Recall tie-break by stable candidate
ID; the frozen evaluator keeps its original NumPy ordering. Aggregate metrics
exclude non-evaluable queries and report total/evaluable/excluded counts. An empty
evaluable population produces null summary metrics. Bootstrap resamples query IDs,
not replicates or seed rows. Paired comparisons require identical query populations,
use their finite intersection, and report excluded pair counts.

## Planning and local verification

Configurations contain an explicit ordered list of jobs and dependencies. There
is no automatic Cartesian expansion. The normalized JSON and TSV assign one row
per job and label scientific stage, execution mode and estimated resource class.
Dependencies must preserve dataset, policy, split, seeds and upstream representations.

Run IDs hash canonical configuration, model/data versions, policy version,
relevance definitions, dependency IDs, git commit, relevant source/fixture hashes
and package versions. Unrelated dirty-worktree state is excluded.
Manifests include these inputs, runtime environment, random seeds, bootstrap settings
and output checksums. Source hashes include uncommitted implementation files.
Workers reject code/environment drift and corrupted plans; regenerate on the target
machine after installing the intended environment. Output and absolute local paths
stay in ignored `outputs/` or external scratch storage.

```bash
.venv/bin/python -m pytest tests/test_benchmark_v2.py -q
.venv/bin/python -m perturb_lm.sklearn_api.execution plan \
  configs/benchmark_v2/synthetic_smoke.yaml --out outputs/benchmark_v2/smoke
for row in 0 1 2 3; do
  .venv/bin/python -m perturb_lm.sklearn_api.execution run \
    --plan outputs/benchmark_v2/smoke/plan.json --row "$row" \
    --out outputs/benchmark_v2/smoke/runs
done
```

The synthetic worker executes embedding, alignment, retrieval and bootstrap as
separate resumable jobs. It supports the deliberately small word-TF-IDF /
CellProfiler-fixture / ridge path. A completion file is atomically published after
output checksums are available. Corrupt or partial outputs rerun; exclusive lock
files prevent concurrent retries. After a killed process, verify no worker remains
before manually removing a stale `.running` file.

## Biowulf scaffolding

`slurm/benchmark_v2/{embedding,alignment,retrieval,bootstrap}.sbatch` supports array
row selection, offline execution and a configurable `BENCHMARK_PYTHON`. The planner
can write a submission shell script with CPU/GPU/memory/time flags, external logs
and `afterok` dependencies. Equivalent jobs can share an array. Plan-only jobs are
not emitted as runnable submissions.

```bash
.venv/bin/python -m perturb_lm.sklearn_api.execution plan \
  configs/benchmark_v2/synthetic_smoke.yaml --out outputs/benchmark_v2/slurm_preview \
  --log-root /tmp/perturb_lm_v2_logs
bash -n outputs/benchmark_v2/slurm_preview/submit.sh
```

This generates and syntax-checks commands; it does not submit them. On Biowulf,
regenerate the plan in the selected environment, use a scratch log/output root,
and set the local interpreter/data root. Resource requests are estimates. Site
module versions, allocation, filesystem paths and scheduler policy need target-side
review. No remote or Biowulf execution was attempted.

## Original Turn 2 work list

This list records the original handoff. Current behavior and review corrections
are described in [the final review](BENCHMARK_V2_FINAL_REVIEW.md). Real execution
remains blocked; the CLI only executes the synthetic chain and frozen checks.

1. Obtain/inspect the missing reference commit and reconcile it with the recorded
   local provenance; retain all frozen source/results until differences are reviewed.
2. Link a reviewed experiment issue and approve real M1/M5 field/rendering contracts,
   annotation provenance, relevance definitions and intended transfer split keys.
3. Implement raw-format adapters and metadata harmonization for the expanded datasets;
   inventory licenses/access and pin real metadata/representation checksums. The
   all-zero hashes and pending revisions in the expanded example are plan-only markers.
4. Implement BM25 and optional model backends, pin weights/pooling/tokenization and
   immutable revisions, and add image/morphology inference plus neural alignments.
   Registry entries are family reservations, not validated backend implementations.
   BAAI/bge-base-en-v1.5 is the proposed general-domain retrieval comparator.
5. Add reviewed real-data workers, model/cache artifact schemas, training eligibility
   exclusions and image/replicate aggregation; validate controls under identical splits.
6. Replan on Biowulf after environment/storage/resource review and explicitly authorize
   execution. Do not reuse a locally generated environment identity for that run.

First safe Turn 2 command:

```bash
.venv/bin/python -m pytest tests/test_benchmark_v2.py -q
```
