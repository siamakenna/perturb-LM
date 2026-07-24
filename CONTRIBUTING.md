# Contributing to Perturb-LM

Perturb-LM is a research benchmark and public prototype. Reproducibility and scientific claim boundaries are part of code quality.

## Two-Person Workflow

- Makenna Rodriguez (`@siamakenna`) is the repository maintainer.
- `@adamdiaz313-collab` is the collaborating contributor.
- All changes must use a branch and pull request.
- One review from the other collaborator is required before merging.
- Do not push directly to `main`.
- Record meaningful scientific and project decisions in issues or pull-request discussions.

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest
python scripts/check_public_copy_consistency.py
```

For the web app:

```bash
cd apps/web
corepack enable
pnpm install --frozen-lockfile
pnpm run lint
pnpm run typecheck
pnpm run test
pnpm run build
```

Phase 3C model inference requires:

```bash
python -m pip install -e ".[phase3c,dev]"
```

## Branch Naming

Use `feature/...`, `fix/...`, `docs/...`, `experiment/...`, or `chore/...`.

## Research and Data Rules

Never commit raw or row-level datasets, embeddings, indexes, projections, model weights, model caches, generated outputs, credentials, `.env` files, or private filesystem paths.

Synthetic smoke results validate software behavior only. They are not scientific evidence.

Changes to query construction, splits, leakage exclusions, relevance definitions, metrics, or baseline definitions require a dedicated issue and explicit review before implementation.

## Pull Requests

Every pull request should link an issue when practical, explain what changed and why, list exact validation commands, label outputs as synthetic/real/pending/public-safe, update tests and documentation when behavior changes, and preserve `docs/CLAIMS_LADDER.md`.

## Licensing

Software licensing and institutional ownership remain under review. Do not add or change a license without an explicit maintainer decision and any required institutional review.
