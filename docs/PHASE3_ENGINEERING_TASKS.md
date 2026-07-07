# Phase 3 Engineering Tasks

This is the recommended task board for the engineering collaborator.

## Highest Priority

| Task | Output | Acceptance |
| --- | --- | --- |
| Index save/load validation | tests and metadata checks | reloaded index returns deterministic nearest neighbors on fixtures |
| Runtime and memory logging | compact JSON summaries | every major baseline run reports row count, dimension, elapsed time, and memory if available |
| Split report export | CSV/JSON split summaries | train/test rows, perturbations, batches, plates, wells, and non-evaluable counts are reported |
| Artifact manifest hardening | manifest JSON schema | every generated run names inputs, commands, outputs, file sizes, and git commit when available |
| Leakage dashboard summaries | small public-safe JSON | dashboard can show warnings without exposing row-level data |

## Medium Priority

| Task | Output | Acceptance |
| --- | --- | --- |
| Optional FAISS backend | optional dependency path | sklearn backend remains default and tests pass without FAISS |
| Embedding dimension validator | CLI check or library utility | mismatched embedding files fail before indexing |
| Local image path validator | report CSV/JSON | missing image files and channels are counted without downloading archives |
| Composite thumbnail workflow | ignored local thumbnails | tiny fixture test covers rendering behavior |
| Report comparison utility | Markdown or JSON diff | two runs can be compared for metrics, leakage, and missing-data changes |

## Do Not Start Yet

- large-scale model training
- full raw image archive download
- cloud-hosted row-level data browser
- biological retrieval claims
- supervised training that leaks labels into held-out evaluation

Before opening any pull request, run:

```bash
git status --short
```

Generated data, embeddings, indexes, model files, and raw image artifacts should not appear as staged changes.

## First Suggested Pull Request

Title:

```text
Add Phase 3 artifact manifest and index validation checks
```

Scope:

- add deterministic save/load tests for current index code
- extend index metadata with input file size, row count, embedding dimension, and command args
- add a compact JSON run manifest for index builds
- update `docs/ARTIFACT_MAP.md` and `docs/PHASE3_ENGINEERING_HANDOFF.md`

Why this first:

The benchmark will need trustworthy artifacts before stronger models are useful.

## Second Suggested Pull Request

Title:

```text
Add held-out split reporting and leakage summary exports
```

Scope:

- write split composition summaries
- report non-evaluable query counts for each split/filter
- export small dashboard-safe leakage summaries
- add tests using synthetic fixtures only

Why this second:

It turns baseline scores into interpretable evidence instead of raw performance numbers.
