# Phase 3A JUMP Real-Data Readiness

> **Status: Historical readiness report.** This report records aggregate results from the Phase 3A local real-data readiness pass. Do not reinterpret these results as learned-model evidence.

Date: 2026-07-21

Branch: `phase3a-jump-real-data-readiness`

Starting commit: `b9e7b10fa1b50d0d8475626fb4c30fd78c42a1bb`

## Scope

This is an engineering and baseline-readiness assessment for a small real local JUMP CPJUMP1 profile dataset. It validates the existing audit, indexing, diagnostics, text-control, artifact-manifest, and readiness-check workflow.

This report is not proof of biologically meaningful natural-language retrieval.

No model development, encoder training, FAISS backend work, raw microscopy image download, row-level data publication, or biological claim was performed.

## Data Inventory

The local assets were consistent with real CPJUMP1 profile and metadata tables, not synthetic fixtures.

| Item | Aggregate Result |
| --- | ---: |
| Candidate local files | 17 |
| Expected metadata files | 5 |
| Profile files | 12 |
| Missing expected metadata files | 0 |
| Aggregate candidate file size | ~13.5 MB |
| File formats | TSV and compressed tables |
| Indexed profile rows | 4,524 |
| Numeric morphology features | 904 |

Detected labels:

| Label Type | Availability |
| --- | --- |
| Batch | available by path inference only |
| Plate | available |
| Well | available |
| Treatment | available |

## Commands

Bounded pilot:

```bash
.venv/bin/python scripts/run_phase2_local_report.py \
  --data-root data/raw/jump_pilot \
  --out outputs/jump_pilot_real_baseline_pilot \
  --max-rows 5000 \
  --top-k 1 5 10 \
  --seed 0

.venv/bin/python scripts/check_phase2_readiness.py \
  --root outputs/jump_pilot_real_baseline_pilot \
  --out outputs/jump_pilot_real_baseline_pilot/readiness_check.json
```

Full local baseline:

```bash
.venv/bin/python scripts/run_phase2_local_report.py \
  --data-root data/raw/jump_pilot \
  --out outputs/jump_pilot_real_baseline \
  --top-k 1 5 10 \
  --seed 0

.venv/bin/python scripts/check_phase2_readiness.py \
  --root outputs/jump_pilot_real_baseline \
  --out outputs/jump_pilot_real_baseline/readiness_check.json
```

The bounded pilot and full run covered the same 4,524 available profile rows.

## Readiness Result

| Check Group | Result |
| --- | ---: |
| Ready flag | true |
| Checks | 16 |
| Failures | 0 |
| Warnings | 1 |

Readiness warning:

- Batch labels were inferred from paths; batch generalization should be verified with more than one real batch before stronger claims.

## Profile Neighbor Leakage Diagnostics

Top-K values: 1, 5, 10

Seed: 0

| Filter | Metric | Evaluable Queries | Rate, All Queries | Rate, Evaluable Queries |
| --- | --- | ---: | ---: | ---: |
| unfiltered | same batch @1 | 4,524 | 1.0000 | 1.0000 |
| unfiltered | same plate @1 | 4,524 | 0.6375 | 0.6375 |
| unfiltered | same well @1 | 4,524 | 0.1379 | 0.1379 |
| unfiltered | same treatment @1 | 4,190 | 0.1512 | 0.1632 |
| exclude same plate | same treatment @1 | 4,190 | 0.2098 | 0.2265 |
| exclude same well | same treatment @1 | 762 | 0.0254 | 0.1509 |
| exclude same plate and well | same treatment @1 | 762 | 0.0212 | 0.1260 |
| exclude same plate and well | same treatment @5 | 762 | 0.0245 | 0.1457 |
| exclude same plate and well | same treatment @10 | 762 | 0.0272 | 0.1614 |

Interpretation:

- Same-batch diagnostics are uninformative because the current local profile subset contains one inferred batch.
- Same-plate signal is high in the unfiltered profile-neighbor diagnostics.
- After excluding both same-plate and same-well neighbors, treatment-evaluable queries fall from 4,190 to 762.
- The remaining same-treatment signal under the strictest filter is measurable but sparse.

## Text-To-Profile Controls

All four required control modes ran with 641 evaluable text queries.

| Mode | mAP | Hit@1 | Hit@5 | Hit@10 | Recall@1 | Recall@5 | Recall@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| full metadata TF-IDF | 0.9952 | 0.9906 | 0.9938 | 0.9984 | 0.1660 | 0.8067 | 0.9784 |
| identifier-stripped TF-IDF | 0.3991 | 0.2496 | 0.4774 | 0.5835 | 0.0504 | 0.2508 | 0.4921 |
| random | 0.0032 | 0.0000 | 0.0078 | 0.0156 | 0.0000 | 0.0014 | 0.0026 |
| shuffled-label | 0.0017 | 0.0000 | 0.0062 | 0.0156 | 0.0000 | 0.0008 | 0.0021 |

Interpretation:

- The full metadata TF-IDF control is dominated by direct metadata lookup and should not be treated as biological retrieval.
- The identifier-stripped TF-IDF control is the more relevant lexical baseline for future model comparisons.
- Any Phase 3A model should beat the identifier-stripped control under held-out perturbation and leakage-aware evaluation, not merely beat random or shuffled-label controls.

## Held-Out Split Summaries

| Split | Train Rows | Test Rows | Train Treatments | Test Treatments | Treatment Overlap | Evaluable Queries | Warnings |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| held-out plate | 3,757 | 767 | 641 | 640 | 640 | 699 | 0 |
| held-out well | 3,618 | 906 | 522 | 139 | 20 | 131 | 0 |
| held-out batch | 4,524 | 0 | 641 | 0 | 0 | 0 | 2 |
| held-out treatment | 3,681 | 843 | 513 | 128 | 0 | 0 | 0 |

Split limitations:

- Held-out batch is unavailable with this local subset because only one inferred batch is present.
- Held-out treatment has no treatment overlap by design, so it is appropriate for testing generalization to unseen treatments, not direct same-treatment retrieval.
- Held-out well leaves only 131 evaluable overlap queries.

## Runtime And Memory

Index artifact runtime summary:

| Field | Value |
| --- | ---: |
| Index runtime | 8.45 seconds |
| Python allocation peak | ~234 MB |
| Process peak memory | ~808 MB |

The full end-to-end report command took several minutes locally because text-control scoring and leakage-aware diagnostics run across the full profile subset. The generated runtime log currently covers index construction, not the entire report command.

## Code Defect Found

A concrete diagnostics scalability defect was discovered during the bounded pilot: the profile-neighbor diagnostics path carried per-candidate dictionaries through large nearest-neighbor candidate lists.

The smallest fix was made in this branch:

- use compact integer neighbor arrays in the JUMP diagnostics path;
- preserve existing aggregate diagnostic behavior;
- add regression coverage for compact neighbor filtering.

## Public-Safety Checks

Generated outputs stayed local and ignored by git.

Dashboard-safe leakage summaries were checked for absence of:

- absolute local paths;
- generated output paths;
- row-level profile identifiers;
- raw/internal diagnostic fields;
- internal metadata column names;
- image filenames;
- embedding and index artifact references.

## Decision

Recommendation: **conditional go** for the first frozen biomedical text-encoder alignment experiment.

Rationale:

- The real local profile pipeline completed.
- Readiness reported 0 failures.
- Random, shuffled-label, full metadata TF-IDF, and identifier-stripped TF-IDF controls are present.
- Leakage behavior is measured.
- Strict same-plate and same-well filtering leaves measurable but sparse treatment-evaluable queries.
- The main limitation is batch generalization: this local subset has one inferred batch, so batch-level generalization is not established.

Recommended next experiment:

```text
Frozen biomedical text encoder with a small linear projection into the JUMP morphology/profile embedding space, evaluated using held-out treatments and leakage-aware plate/well controls.
```

The experiment should remain a controlled retrieval baseline until it beats identifier-stripped metadata controls under the same split and leakage conditions.
