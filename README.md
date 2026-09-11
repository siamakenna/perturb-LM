# Perturb-LM: Leakage-Aware Language Retrieval of Cell Painting Morphology


<!-- BIWULF_STRICT_20260911 -->
## Latest strict benchmark update — 2026-09-11

A strict leakage-aware benchmark has now been reproduced using a
`held_out_plate` split with same-plate and same-well retrieval candidates
excluded.

| Method | mAP | 95% query-bootstrap CI | Total queries | Evaluable |
| --- | ---: | ---: | ---: | ---: |
| Identifier-stripped TF-IDF | 0.157407 | 0.137431–0.179733 | 1,079 | 180 |
| BiomedBERT, unaligned | 0.009196 | 0.005982–0.013334 | 1,079 | 180 |
| BiomedBERT, train-only ridge projection | 0.033156 | 0.019586–0.048473 | 1,079 | 180 |

Projection improves the dense BiomedBERT baseline but does not close the
gap to identifier-stripped TF-IDF under this strict evaluation. This does
not imply that TF-IDF understands biology better; it describes the
performance of this specific frozen encoder plus linear-alignment setup.

MedCPT and BioLORD-2023 have also been pinned to immutable model revisions
and successfully validated offline. Their Perturb-LM comparator scores are
still pending.

See:

- [Strict benchmark reproduction](docs/BIWULF_STRICT_BENCHMARK_2026-09-11.md)
- [Comparator model validation](docs/COMPARATOR_MODEL_VALIDATION_2026-09-11.md)
- [Metadata and preprocessing audit](docs/METADATA_AND_PREPROCESSING_AUDIT.md)

Perturb-LM is a research benchmark for asking whether natural-language descriptions of biological perturbations can retrieve Cell Painting morphology profiles for the right reasons.

The project is intentionally conservative. Treatment identifiers, target sequences, replicate structure, plate effects, well effects, and batch effects are treated as core evaluation risks rather than after-the-fact cleanup.

> **Our rule:** A strong score is not automatically a true positive, and a weak score is not automatically a true negative. We only call a result when the controls, coverage, uncertainty, and reproducible rerun tell the same story.

## Research question

Can frozen biomedical language representations retrieve perturbation-induced cellular morphology better than strong identifier-stripped lexical controls under held-out and leakage-aware evaluation?

## Why this benchmark exists

Cell Painting screens capture rich treatment-induced cellular phenotypes, but natural-language search can look successful for misleading reasons. A model may retrieve the expected perturbation because the text contains a compound name, target sequence, plate label, or another acquisition shortcut rather than because the representation captures morphology-relevant biology.

Perturb-LM makes those shortcuts visible. It also guards against the opposite problem: calling a model failure when strict filtering, incomplete labels, missing positives, or an overly narrow relevance definition make the task nonevaluable.

Results are therefore described as:

- **supported** when the method clears the predefined controls with adequate coverage and uncertainty;
- **not supported under this evaluation** when it does not;
- **inconclusive** when the data, candidate coverage, or evaluation design cannot distinguish the two.

## Current evidence

### Validated in the current repository

The active public repository supports the benchmark foundation and lexical controls below.

| Item | Current value |
| --- | ---: |
| Dataset track | JUMP CPJUMP1 profiles |
| Input files | 12 files from `2020_11_04_CPJUMP1` |
| QC profiles | 4,524 |
| Profiles entering scored retrieval | 4,190 |
| Excluded for missing treatment label | 334 |
| Primary morphology features | 904 |
| Evaluable full lexical queries | 641 / 641 |
| Identifier-stripped TF-IDF mAP | 0.2513 |
| mAP 95% query-bootstrap CI | 0.2445 to 0.2582 |
| Held-out batch | unavailable |

The 4,524 count is the QC inventory. Only the 4,190 profiles with non-missing treatment labels enter scored retrieval. The identifier-stripped TF-IDF score is a lexical control, not a learned-model result.

### New abstract-reported analysis under reconciliation

The current project abstracts report a later strict held-out-plate analysis. These numbers are being cross-checked against a clean-clone run and a frozen result manifest before they are promoted to validated repository claims.

| Strict held-out-plate result | Abstract-reported value |
| --- | ---: |
| Total queries | 1,079 |
| Evaluable queries after strict exclusions | 180 |
| Identifier-stripped TF-IDF mAP | 0.1574 |
| TF-IDF 95% CI | 0.1367 to 0.1795 |
| Unaligned BiomedBERT mAP | 0.0092 |
| Ridge-projected BiomedBERT mAP | 0.0332 |
| Projected BiomedBERT vs. TF-IDF | -0.1243 mAP |
| Paired 95% CI | -0.1519 to -0.0946 |

These results should not be directly substituted for the 641-query lexical benchmark. They use a different split/filter population. The immediate reproducibility task is to link every number to its exact query population, split, leakage filter, command, commit, checksum, and generated aggregate artifact.

The narrow working interpretation is:

> Linear projection improved BiomedBERT relative to the unaligned representation, but it did not beat the identifier-stripped TF-IDF control under the tested settings.

This does **not** establish that all biomedical language models fail at morphology retrieval. It shows that off-the-shelf BiomedBERT with this controlled linear alignment was not sufficient under these evaluation conditions.

## What counts as a solid output

Every headline result should include:

1. the exact dataset and split-specific profile population;
2. total, evaluable, and nonevaluable query counts, with exclusion reasons;
3. random, shuffled-label, full-metadata TF-IDF, and identifier-stripped TF-IDF controls;
4. leakage status for identifiers, target sequences, plate, well, batch, filenames, and lookup keys;
5. paired query-bootstrap confidence intervals and per-query differences;
6. both ranking quality and coverage metrics, including mAP/Hit@K and Recall@K;
7. a reproducibility record with commit SHA, checksums, model revision, seed, environment, command, runtime, and warnings.

### Avoiding misleading positives

- Direct identifiers or duplicate metadata wording must not act as lookup keys.
- Preprocessing, hyperparameter selection, treatments, and replicates must not leak across splits.
- Beating random alone is not success; a candidate must beat identifier-stripped TF-IDF under the same evaluation.
- The full predefined split/filter matrix must be reported rather than selecting one favorable condition.
- Mean performance must be paired with subgroup and per-query error analysis.

### Avoiding misleading negatives

- Nonevaluable queries are counted and explained rather than silently dropped.
- Evaluable and nonevaluable query groups are compared for selection bias.
- Exact-treatment relevance is the primary task; pathway- or mechanism-level relevance must be separately defined and biologically reviewed.
- One encoder and one linear projection are not treated as the ceiling for multimodal alignment.
- Low recall is checked against label quality, candidate coverage, replicate availability, and one-batch limitations.

## Benchmark design

### Query text policy

Identifier-stripped model input may use:

- `Metadata_gene`
- `Metadata_pert_type`
- `Metadata_control_type`
- `Metadata_negcon_control_type`

It must exclude:

- target sequences;
- treatment and sample identifiers;
- compound names, SMILES, and InChIKeys;
- plate, well, and batch labels;
- profile IDs, filenames, source paths, and source row numbers.

The run must fail before encoding if prohibited values appear in supposedly identifier-stripped text.

### Required methods

1. random retrieval;
2. shuffled-label retrieval;
3. full-metadata TF-IDF as an intentional identifier-dominated reference;
4. identifier-stripped TF-IDF as the primary lexical control;
5. frozen BiomedBERT embeddings as an unaligned control;
6. train-only ridge projection from BiomedBERT into the 904-feature morphology space.

### Required splits and filters

- unfiltered retrieval;
- exclude same plate;
- exclude same well;
- exclude same plate and well;
- held-out plate;
- held-out treatment;
- held-out batch when multiple batches become available.

Held-out batch generalization is currently unavailable because the primary benchmark contains one inferred batch.

### Required metrics

- mean average precision;
- Hit@1, Hit@5, and Hit@10;
- Recall@1, Recall@5, and Recall@10;
- total and evaluable query counts;
- same-plate, same-well, same-batch, and same-treatment rates where available;
- paired difference from identifier-stripped TF-IDF;
- paired query-bootstrap 95% confidence interval;
- error analysis across perturbation type, annotation richness, replicate count, and positive-candidate coverage.

## Current priorities

1. Build a result crosswalk connecting the current abstracts to exact commands and output artifacts.
2. Reproduce held-out-plate and held-out-treatment results from a clean clone at a frozen commit.
3. Audit why 180 of 1,079 queries remain evaluable in the primary strict condition.
4. Confirm that the 4,190-profile inclusion rule is applied before splitting and that the separate 192-profile Day 1 set remains excluded.
5. Verify all random, shuffled-label, lexical, unaligned, and projected runs under identical candidate pools and filters.
6. Produce a small public-safe aggregate bundle capable of regenerating manuscript tables and figures.
7. Align the README, methods, claims ladder, abstract seed, manuscript, and public prototype after the evidence package passes review.

## Planned paper

The paper is framed as a benchmark and responsible-evaluation study rather than a claim of completed biological discovery.

Working title:

> **Perturb-LM: Leakage-Aware Evaluation of Natural-Language Retrieval for Cell Painting Morphology**

Core paper components:

- dataset and query population flow;
- identifier-removal and leakage-audit protocol;
- held-out-plate and held-out-treatment evaluation;
- strong lexical and stochastic controls;
- per-query uncertainty and evaluability accounting;
- error analysis covering both likely false positives and likely false negatives;
- narrow claims that distinguish model limitations from benchmark limitations.

## Roadmap

### Next: make the benchmark hard to fool

- complete clean-clone reproduction and the result crosswalk;
- finalize negative controls and the evaluability audit;
- create manuscript-ready, public-safe aggregate outputs;
- keep the claims ladder synchronized with the evidence.

### Then: test better alignment without moving the goalposts

- compare additional biomedical and scientific text encoders;
- test morphology-specific contrastive alignment;
- use plate-aware and treatment-aware hard negatives;
- compare linear and carefully regularized nonlinear alignment;
- add retrieval calibration and an abstention option for low-evidence matches.

### Later: broaden the data and biological relevance

- evaluate multiple JUMP batches and an independent Cell Painting dataset;
- connect the existing RxRx manifests, image paths, composite QA, embeddings, and indexes to real-data experiments;
- compare aggregate morphology features with learned image embeddings;
- evaluate expert-reviewed pathway and mechanism relevance;
- develop a focused neurodegeneration use case;
- release versioned splits, baseline implementations, and uncertainty-aware benchmark artifacts.

## Repository structure

| Path | Purpose |
| --- | --- |
| `src/perturb_lm/` | Data loading, retrieval, diagnostics, modeling contracts, and reporting |
| `scripts/` | Reproducible command-line workflows and consistency checks |
| `tests/` | Synthetic fixtures and regression tests |
| `docs/` | Methods, claims, readiness reports, setup references, and collaborator guidance |
| `apps/web/` | Next.js public research prototype |
| `configs/` | Experiment and validation configuration |

## Minimal quick start

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest
```

Run the website locally:

```bash
cd apps/web
pnpm install --frozen-lockfile
pnpm dev
```

Detailed smoke, real-data, reporting, and modeling commands live in the documentation.

## Public prototype

[Open the public Perturb-LM research prototype](https://web-pi-wheat-64.vercel.app)

The current demo is explicitly synthetic:

> Illustrative interface demo - not real model output

The deployment provides an interface and public-safe aggregate dashboard only. It does not expose real row-level data, embeddings, model weights, or generated indexes.

## Documentation

Start with:

- [Documentation index](docs/README.md)
- [Methods draft](docs/METHODS_DRAFT.md)
- [Claims ladder](docs/CLAIMS_LADDER.md)
- [Evaluation protocol](docs/EVALUATION_PROTOCOL.md)
- [Phase 3C alignment plan](docs/PHASE3C_TEXT_PROFILE_ALIGNMENT.md)
- [Phase 3C compute environment](docs/PHASE3C_COMPUTE_ENVIRONMENT.md)
- [Known-good local run checklist](docs/KNOWN_GOOD_LOCAL_RUN.md)
- [Collaborator handoff](docs/COLLABORATOR_HANDOFF.md)
- [Real RxRx setup](docs/REAL_RXRX_SETUP.md)

## Collaboration and review

- Maintainer: [`@siamakenna`](https://github.com/siamakenna)
- Current collaborator: [`@adamdiaz313-collab`](https://github.com/adamdiaz313-collab)

Work should use issues, branches, pull requests, and review. Decisions affecting benchmark definitions, scientific interpretation, public claims, submission scope, authorship, or licensing should be recorded in an issue or pull request.

Authorship is based on intellectual and practical contributions, not GitHub access or commit count.

## Data and artifact policy

Raw image archives are not downloaded by default. Metadata and morphology profiles are used first, and image downloads remain opt-in.

Do not commit real data, embeddings, generated outputs, model weights, indexes, row-level results, `.env`, virtual environments, credentials, or private local paths. Generated artifacts belong under ignored locations such as `data/`, `outputs/`, `results/`, `models/`, or `.cache/`.

## Citation

Perturb-LM is an active research prototype. A manuscript citation is not available yet. Until then, cite this repository and the exact commit or release used.

