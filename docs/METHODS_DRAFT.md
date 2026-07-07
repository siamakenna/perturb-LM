# Methods Draft

This is a working methods skeleton for the current reproducibility benchmark. It is not a manuscript.

## Objective

Perturb LM evaluates text-conditioned retrieval over high-content microscopy perturbation datasets. The current Phase 2 objective is narrower: validate real-data metadata/profile baselines and leakage behavior before training or claiming biological retrieval.

## Dataset Track

The active real-data track is JUMP CPJUMP1 morphology profiles stored locally under:

```text
data/raw/jump_pilot/
```

Raw microscopy image archives are not downloaded by default. Generated outputs remain local under `outputs/`.

## Profile Inventory

Local profile and metadata files are audited with:

```bash
python scripts/audit_jump_pilot.py
```

The audit records metadata files, profile files, detected metadata columns, detected numeric feature columns, likely batch/plate/well columns, and treatment-label columns.

## Profile Index

Profile rows are loaded from local CPJUMP1 profile tables. Numeric Cell Painting features are detected and L2-normalized. A sklearn nearest-neighbor index with cosine distance is built for local baseline diagnostics.

## Profile-Neighbor Diagnostics

The diagnostic script computes same-label nearest-neighbor behavior for:

- batch
- plate
- well
- treatment label

Same-treatment retrieval is compared against random and shuffled-label controls. Filtered presets remove same-plate, same-well, and same-plate-plus-well neighbors before scoring same-treatment retrieval.

## Text-To-Profile Metadata Baselines

Metadata-derived text queries are generated from treatment labels and available profile metadata.

The current baselines are:

- `metadata_tfidf`: TF-IDF over profile metadata text, including direct perturbation identifiers.
- `identifier_stripped_tfidf`: TF-IDF with direct perturbation IDs/names removed from candidate text.
- `random`: random score control.
- `shuffled_label`: original scores with shuffled treatment labels.

The identifier-stripped baseline is the stronger control for future models.

## Metrics

Reported metrics include:

- mean average precision
- hit@K
- recall@K
- number of evaluable queries
- positive cross-batch, cross-plate, and cross-well counts
- random and shuffled-label controls

## Reproducibility Artifacts

The one-command runner writes:

```bash
python scripts/run_phase2_local_report.py
```

Outputs include a machine-readable `baseline_manifest.json`, per-step JSON/CSV summaries, and a Markdown report.

## Scope And Limitations

Current results validate profile and metadata-control retrieval plumbing. They do not prove biological image understanding. Current local CPJUMP1 data may contain one inferred batch, so batch generalization must be tested before Phase 3 claims.

## Phase 3 Entry Requirement

Phase 3 model work should start only after:

- readiness checks pass
- local real-data baselines are reproducible
- metadata controls are reported
- held-out split behavior is measured
- no generated artifacts or data are tracked by git
