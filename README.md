# Perturb-LM: Leakage-Aware Language Retrieval of Cell Painting Morphology

Perturb-LM is a research benchmark for asking whether natural-language descriptions of biological perturbations can retrieve Cell Painting morphology profiles. The project is intentionally conservative: it treats treatment identifiers, target sequences, replicate structure, plate effects, well effects, and batch effects as core evaluation risks rather than after-the-fact cleanup.

The current repository validates a text-to-morphology-profile benchmark on a local JUMP CPJUMP1 profile subset. It does not yet claim validated biological natural-language retrieval, text-to-image retrieval, clinical utility, or learned-model success.

## Research Question

Can frozen biomedical language representations retrieve perturbation-induced cellular morphology better than strong identifier-stripped lexical controls under held-out and leakage-aware evaluation?

## Scientific Problem

Cell Painting screens measure rich morphology across thousands of perturbations, but search systems can look impressive for the wrong reasons. A model may retrieve the right perturbation because the text contains a compound name, a sequence, a plate label, or another acquisition shortcut rather than because the language representation captures morphology-relevant biology.

Perturb-LM focuses on making those shortcuts visible before stronger claims are made. The scoring unit is perturbation-level retrieval after profile-level ranking, and every future learned method must be compared against lexical and stochastic controls under explicit split and leakage settings.

## Current Benchmark

The active benchmark uses public-safe aggregate reporting only. Row-level data, local paths, image names, embeddings, generated indexes, and model outputs are not committed.

| Item | Current value |
| --- | ---: |
| Dataset track | JUMP CPJUMP1 profiles |
| Profiles | 4,524 |
| Primary morphology features | 904 |
| Full benchmark queries | 641 |
| Identifier-stripped TF-IDF mAP | 0.2513 |
| mAP 95% query-bootstrap CI | 0.2445 to 0.2582 |
| Held-out batch | unavailable |
| Learned model result | pending |

The identifier-stripped TF-IDF score is a lexical control, not a learned model result. The learned alignment experiment remains pending until it beats the identifier-stripped control under the specified held-out and leakage-aware evaluations.

## Status And Limitations

Validated now:

- synthetic CI fixtures for parsing, retrieval, splits, diagnostics, reports, and smoke workflows;
- a real local CPJUMP1 profile benchmark foundation with a consistent 904-feature primary space;
- random, shuffled-label, full-metadata TF-IDF, and identifier-stripped TF-IDF controls;
- public-copy checks that prevent pending learned methods from displaying numeric scores;
- a Next.js research prototype with a synthetic demo and public-safe benchmark dashboard.

Pending:

- frozen biomedical text encoder evaluation;
- learned linear projection into the 904-feature morphology space;
- split-specific learned-model results;
- held-out-batch evaluation, which is unavailable because the current local benchmark has one inferred batch;
- validated image-level or text-to-image retrieval.

## Repository Structure

| Path | Purpose |
| --- | --- |
| `src/perturb_lm/` | Data loading, retrieval, diagnostics, modeling contracts, and reporting |
| `scripts/` | Reproducible command-line workflows and consistency checks |
| `tests/` | Synthetic fixtures and regression tests |
| `docs/` | Methods, claims, readiness reports, and setup references |
| `apps/web/` | Next.js public research prototype |
| `configs/` | Experiment and validation configuration |

## Minimal Quick Start

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

Detailed smoke, real-data, reporting, and modeling commands live in the documentation rather than in this README.

## Prototype

The web app includes `/`, `/dashboard`, `/demo`, `/methods`, and `POST /api/search`. The demo is explicitly synthetic:

> Illustrative interface demo — not real model output

A permanent public deployment URL is pending. Local or temporary preview deployments should not be treated as published scientific evidence.

## Documentation

Start with:

- [Documentation index](docs/README.md)
- [Methods draft](docs/METHODS_DRAFT.md)
- [Claims ladder](docs/CLAIMS_LADDER.md)
- [Phase 3C alignment plan](docs/PHASE3C_TEXT_PROFILE_ALIGNMENT.md)
- [Known-good local run checklist](docs/KNOWN_GOOD_LOCAL_RUN.md)
- [Real RxRx setup](docs/REAL_RXRX_SETUP.md)

## Data And Artifact Policy

Full raw image archives are not downloaded by default. Metadata and profiles are used first, and raw image downloads must remain opt-in. Do not commit real data, embeddings, generated outputs, model weights, indexes, row-level result tables, `.env`, or virtual environments. Generated files belong under ignored locations such as `data/`, `outputs/`, `results/`, or `models/`.

## Citation And Contact

Perturb-LM is an active research prototype. A manuscript citation is not available yet. Until then, cite the GitHub repository and the exact commit or release used.
