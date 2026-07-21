# Perturb-LM: Leakage-Aware Language Retrieval of Cell Painting Morphology

Perturb-LM is a leakage-aware benchmark for aligning natural-language descriptions of biological perturbations with Cell Painting morphology profiles. Unlike conventional retrieval setups, it evaluates predictions at the perturbation level and explicitly controls for treatment identifiers, target sequences, replicate structure, plate effects, and well effects.

Using 4,524 CPJUMP1 profiles represented by 904 morphology features, the current foundation establishes reproducible quality control, train-only preprocessing, deterministic evaluation, query-level uncertainty, and strong lexical controls. The next experiment tests whether frozen biomedical text embeddings, aligned through a lightweight projection, can outperform an identifier-stripped TF-IDF baseline under held-out plate and treatment evaluation.

## Research Question

Can frozen biomedical language representations retrieve perturbation-induced cellular morphology better than strong identifier-stripped lexical controls?

## Why Leakage Matters

High-content microscopy screens contain rich perturbation-induced phenotypes, but naive retrieval evaluation can be inflated by non-biological shortcuts:

- direct treatment names or compound identifiers;
- target sequences that uniquely identify an intervention;
- replicate structure;
- plate and well-position effects;
- batch effects;
- inconsistent feature schemas;
- evaluating on the same perturbations used for training.

Perturb-LM treats these as first-order evaluation problems rather than cleanup details.

## Current Benchmark

The active benchmark is text-to-morphology-profile retrieval on JUMP CPJUMP1 Cell Painting profiles. It is not yet validated text-to-image retrieval.

Public-safe aggregate state:

| Item | Current value |
| --- | ---: |
| Profiles | 4,524 |
| Primary morphology features | 904 |
| Full benchmark queries | 641 |
| Identifier-stripped TF-IDF mAP | 0.2513 |
| mAP 95% query-bootstrap CI | 0.2445 to 0.2582 |
| Held-out batch | unavailable |
| Learned model result | pending |

The identifier-stripped TF-IDF result is a lexical control, not a learned model result.

## Current Evidence

Established now:

- the original local CPJUMP1 profile subset has a consistent 904-feature schema;
- the full-query lexical benchmark runs with random and shuffled-label controls;
- target sequences and direct treatment identifiers are prohibited from identifier-stripped query text;
- train-only preprocessing, deterministic query selection, and query-bootstrap uncertainty are implemented;
- split and leakage integrity checks report evaluability instead of silently dropping non-evaluable cases.

The current evidence supports software and benchmark readiness. It does not establish broad biological natural-language retrieval.

## Planned Alignment Experiment

Working hypothesis:

> Frozen biomedical language representations contain enough mechanistic information to support retrieval of perturbation-induced morphology after lightweight alignment, but success must be demonstrated against identifier-stripped lexical controls under held-out and leakage-aware evaluation.

The next model experiment freezes a biomedical text encoder and trains a small regularized linear projection into the existing 904-feature morphology-profile space. The learned projection must outperform identifier-stripped TF-IDF under held-out plate and held-out treatment evaluation. Beating random or shuffled-label controls alone is not enough.

## Quick Start

Install the Python package for local development:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Run the full test suite:

```bash
python -m pytest
```

Run the synthetic smoke workflows:

```bash
python scripts/run_phase1_smoke.py --out outputs/phase1_smoke
python scripts/run_phase2_jump_smoke.py --out outputs/phase2_jump_smoke
python scripts/run_phase3b_projection_smoke.py --out outputs/phase3b_projection_smoke --seed 0
```

Check public-facing copy consistency:

```bash
python scripts/check_public_copy_consistency.py
```

Run the Phase 3C synthetic alignment smoke:

```bash
python scripts/run_phase3c_alignment_smoke.py --out outputs/phase3c_alignment_smoke --seed 0
```

For the optional frozen BiomedBERT encoder path:

```bash
python -m pip install -e ".[phase3c,dev]"
```

When local CPJUMP1 profile files are available, generated reports and indexes should be written under ignored output directories.

## Repository Structure

| Path | Purpose |
| --- | --- |
| `src/perturb_lm/` | Python package for data loading, retrieval, diagnostics, modeling contracts, and reporting |
| `scripts/` | Reproducible command-line workflows and checks |
| `tests/` | Synthetic fixtures and regression tests |
| `docs/` | Methods, claims, reproducibility, and readiness documentation |
| `apps/web/` | Public research prototype website |
| `site/` | Earlier static project dashboard |
| `configs/` | Experiment and validation configuration |

## Reproducibility And Data Policy

Full raw image archives are never downloaded by default. Metadata and profiles are used first, and raw image downloads must remain opt-in. The repository must not commit real profiles, embeddings, generated outputs, model weights, indexes, row-level result tables, `.env`, or virtual environments.

Generated outputs belong under ignored directories such as `outputs/`, `results/`, or `models/`.

Engineering reproducibility references:

- `docs/PHASE3_ENGINEERING_PLAN.md`
- `docs/KNOWN_GOOD_LOCAL_RUN.md`
- `docs/PHASE3_ENGINEERING_TASKS.md`

## Current Limitations

- The real biomedical text-alignment experiment has not started.
- Split-specific learned-model results remain pending.
- Held-out-batch evaluation is unavailable because the current local benchmark has one inferred primary batch.
- An additional profile plate is available only as a compatibility investigation because it changes the feature schema.
- The active benchmark is profile-based; image-level retrieval remains a longer-term direction.
- Perturbation-level aggregation is necessary for evaluation, but it does not automatically make results biologically meaningful.

## Development Roadmap

1. Evaluate frozen biomedical text encoders.
2. Fit and test a regularized linear projection.
3. Run split-specific held-out plate and treatment evaluation.
4. Compare individual and replicate-consensus morphology profiles.
5. Add biologically meaningful hard negatives.
6. Harmonize a second batch for external validation.
7. Link profile-level retrieval to representative microscopy images.
8. Add interpretable morphology attribution.

## Citation Status

Perturb-LM is an active research prototype. A manuscript citation is not available yet. Until then, cite the repository and clearly state the commit or release used.
