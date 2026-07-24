# Collaborator Handoff

## Current Project State

Perturb-LM is a leakage-aware benchmark and public synthetic prototype for natural-language retrieval over Cell Painting perturbation profiles.

Validated benchmark:

- 4,524 CPJUMP1 profiles;
- 904 numeric morphology features;
- 641 benchmark queries;
- identifier-stripped TF-IDF mAP: 0.2513;
- query-bootstrap 95% CI: 0.2445 to 0.2582.

Learned biomedical model results remain pending.

## Collaboration

- Maintainer: `@siamakenna`
- Collaborator: `@adamdiaz313-collab`
- Repository: https://github.com/siamakenna/perturb-LM
- Public prototype: https://web-pi-wheat-64.vercel.app

All work uses issues, branches, pull requests, and one review from the other collaborator.

## First Phase 3C Goal

Establish a reproducible environment and complete a bounded frozen-BiomedBERT embedding run followed by the one-seed Phase 3C evaluation.

Google Colab is a convenient starting option, but it is not required. AWS, RunPod, another Linux environment, or a reproducible local setup are acceptable when exact commands and versions are recorded.

## Required First-Run Record

Save the exact Git commit, environment report, notebook or setup instructions, input checksum, embedding manifest and shape, model revision, seed, full command, runtime/device information, warnings, and leakage-check status.

## Artifact Rules

Keep embeddings, caches, projections, indexes, row-level results, weights, and private paths outside GitHub. Commit only source, tests, documentation, configuration, and reviewed public-safe aggregate summaries.

## Required Reading

1. `docs/CLAIMS_LADDER.md`
2. `docs/EVALUATION_PROTOCOL.md`
3. `docs/PHASE3C_TEXT_PROFILE_ALIGNMENT.md`
4. `docs/KNOWN_GOOD_LOCAL_RUN.md`
5. `docs/DATA_PROVENANCE.md`
6. `CONTRIBUTING.md`
7. `AGENTS.md`

## Handoff Acceptance

The handoff is complete when the collaborator can clone and test the repository, explain the validated baseline and claim boundary, locate approved inputs through a private channel, run the bounded embedding workflow, produce the required manifest/checksum, and open a clean pull request without generated artifacts.
