# Benchmark V2 final review

Scope: the original complete feature branch from merge base
`56ec4d08d2b638d0d1d8b8f559ab32e8f0cc15d0`, including Turn 1 and Turn 2.
At the time of that review, reference
`ccec3b94ea6b5061a2d221c553b15e1fb1a93cc1` was inspected without merging
its later Phase 3C changes. Those changes are now present in the post-merge
history. The post-merge CI repair reconciles the two affected frozen source
checksums without changing scientific metrics or result artifacts.

## Findings corrected

- Run identities included an unrelated dirty-worktree boolean. Identity now uses
  the commit and relevant source checksums; unrelated files cannot change run IDs.
  Plans and completion manifests include the complete relevance definition.
- The synthetic worker recorded a contract while evaluating hardcoded treatment
  relevance. It now validates and executes the selected contract. Its fixture
  explicitly declares treatment retrieval, matching the supplied M0 contract.
- The public pipeline omitted contract approval and identity-aware split checks.
  It now enforces them before fitting, supplies relevance groups to contrastive
  training, and invalidates fitted gallery state after a failed refit. Query
  rendering no longer requires a treatment column independently of relevance.
- The retrieval helper incorrectly compared queries and candidates as train/test
  partitions. It now requires training metadata and checks both held-out populations.
- Held-out identity checks now use the declared relevance identity. Physical well
  overlap is rejected across train/test, with canonical well coordinates. Optional
  `group_fields` enforce an explicit shared replicate-group key; held-out gene and
  compound split kinds are available. A plate split does not imply gene or compound
  independence. Non-transfer identities are scoped by dataset; transfer requires
  explicit mapping provenance and scientific approval.
- Completed runs previously skipped dependency and frozen-reference checks.
  Resumption revalidates these inputs. Embedding and aggregation bundles now have
  checksum-bearing completion markers, and aggregation retains exclusion records.
- Paired aggregation and bootstrap now use both evaluability flags and finite
  paired values, report pair counts, and handle an empty paired population explicitly.
- Model assets must checksum every staged file and are revalidated before inference
  or cache reuse. Cache identity includes dtype, shape, batch size, backend package
  versions, and adapter source. Lazy backend handles are cleared on refit and
  omitted from serialization. Offline HF loading and masked mean/CLS pooling have
  dependency-free adapter tests. BGE pooling was corrected to the official CLS rule.
- Speculative BiomedCLIP/CellCLIP/OpenPhenom loaders are disabled before optional
  imports. Code approval alone cannot enable them. Their pinned assets still need
  reviewed offline architecture/preprocessing adapters, without mutating staged files.
- Neural checkpoints now bind source, training shapes/dtypes, settings, and saved
  state checksums. Exact resume, missing contrastive groups, and corrupted weights
  are tested. BM25 handles empty documents at `b=1` without nonfinite scores.
- Raw-adapter tests preserve leading-zero IDs and join shuffled representation
  caches by ID. Well-level records require complete physical identity metadata.

## Validation commands

Final local validation: 107 focused tests and 237 repository tests passed. Ruff
lint and formatting passed for all 21 Python files changed on the feature branch.
All four synthetic stages completed; all eight frozen checksums matched. Syntax
checks passed for four SLURM templates and five generated shell scripts. The
publication audit of the 40 proposed files and branch history found no credentials,
private machine paths, files over 1 MB, model weights, caches, or bulk outputs.
The small committed metadata CSV is an explicitly synthetic test fixture.
The three pre-existing untracked user directories were preserved and excluded.

Run from the repository root with the project environment:

```bash
.venv/bin/python -m pytest -q tests/test_benchmark_v2.py tests/test_benchmark_v2_turn2.py tests/test_benchmark_v2_review.py
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check src/perturb_lm/sklearn_api tests/test_benchmark_v2*.py
.venv/bin/python -m ruff format --check src/perturb_lm/sklearn_api tests/test_benchmark_v2*.py
git diff --check
for script in slurm/benchmark_v2/*.sbatch; do /bin/bash -n "$script"; done
.venv/bin/python -m perturb_lm.sklearn_api.execution plan configs/benchmark_v2/synthetic_smoke.yaml --out outputs/benchmark_v2/final_review_smoke --log-root /tmp/plm_v2_review_logs
/bin/bash -n outputs/benchmark_v2/final_review_smoke/submit.sh
for row in 0 1 2 3; do
  .venv/bin/python -m perturb_lm.sklearn_api.execution run --plan outputs/benchmark_v2/final_review_smoke/plan.json --row "$row" --out outputs/benchmark_v2/final_review_smoke/runs
done
.venv/bin/python -m perturb_lm.sklearn_api.execution plan configs/benchmark_v2/cpjump1_regression.yaml --out outputs/benchmark_v2/final_review_frozen
.venv/bin/python -m perturb_lm.sklearn_api.execution run --plan outputs/benchmark_v2/final_review_frozen/plan.json --row 0 --out outputs/benchmark_v2/final_review_frozen/runs
```

The read-only publication scan used the ignored local audit script:
` .venv/bin/python outputs/benchmark_v2/final_review_publication_audit.py `.
It checks changed paths, sizes, asset extensions, private paths, and credential
patterns in the final files and every new commit. It prints finding categories
and filenames rather than potential secret contents.

Regenerate plans after a code/configuration/environment change or commit. Generated
artifacts remain under ignored `outputs/`. SLURM tests use a fake `sbatch`; shell
syntax and quoting tests do not constitute Biowulf execution validation.

## Remaining production gates

This is a synthetic-tested infrastructure branch, not a completed real-data
benchmark. All supplied relevance contracts require scientific approval for real
execution. M1/M5 remain provisional and synthetic-only. Experimental opt-in does
not override that restriction. Real CLI dispatch is not implemented and cannot
be enabled by editing the execution flag; reviewed production integration is needed.

Before a real run, approve dataset harmonization, namespaces, dose/timepoint/species
fields, replicate/site aggregation, leakage split keys, and the independent query
population. The bootstrap resamples query IDs with equal weight; it assumes those
units are independent. Correlated record queries require an approved clustering or
query-aggregation design before scientific confidence intervals can be reported.
No raw-adapter schema check establishes biological matching or data availability.

Stage approved data and immutable model assets with full checksums, review optional
model code/licenses and backend adapters, and validate the target environment,
storage paths, scheduler resources, and one synthetic job on Biowulf first.
Blockers: `needs_scientific_approval`, `needs_data`, `needs_model_prefetch`,
`needs_backend_review`, `needs_production_worker`, `needs_biowulf_validation`.
