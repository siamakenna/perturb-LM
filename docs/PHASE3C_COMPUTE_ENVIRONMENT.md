# Phase 3C Compute Environment

Issue #27 selects the reproducible compute target for the frozen BiomedBERT
experiment. This page documents environment choice only. It does not authorize
model training, embedding generation, large downloads, or committing generated
artifacts.

## Recommended Default

Use Google Colab or another Linux GPU environment as the preferred Phase 3C run
target.

Recommended runtime:

- Python `>=3.10`
- package install: `python -m pip install -e ".[phase3c,dev]" -c constraints/phase3c.txt`
- frozen encoder: `microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext`
- pinned model revision: `e1354b7a3a09615f6aba48dfad4b7a613eef7062`
- device request: `auto`, which uses CUDA when available, then Apple MPS, then CPU
- persistent storage: `/content/drive/...` on Colab or ignored local storage under
  `$PROJECT_ROOT`

Rationale:

- Linux GPU runtimes reduce CUDA and package drift relative to ad hoc laptops.
- Colab can be started from a fresh clone and a small set of recorded commands.
- GPU acceleration keeps frozen encoder inference practical without changing the
  experiment into model training.
- Persistent Drive-backed cache and output locations survive runtime resets while
  still staying outside Git.
- The same public-safe environment report can be run locally for dry-run tests
  and in the final runtime that generates the actual local-only artifacts.

## Acceptable Alternates

These alternatives are acceptable when the exact environment is recorded:

- Linux CUDA GPU host, such as RunPod, AWS, or institutional GPU infrastructure.
- Linux CPU host for small or slower frozen-encoder runs.
- Local Windows for documentation, synthetic tests, and command dry runs.
- Local Windows GPU only when `torch`, CUDA availability, GPU name, VRAM, package
  versions, commit, branch, and dirty status are recorded from the actual run.

Final embedding and evaluation runs should record the actual runtime used. Local
Windows dry runs are useful, but they are not a substitute for the final runtime
record if embeddings are produced elsewhere.

## Required Run Record

Run the public-safe environment reporter before a final Phase 3C embedding or
evaluation run:

```bash
python scripts/print_environment_report.py
```

Record these fields in the local run notes or generated local manifest:

- exact git commit
- branch name
- git dirty status
- Python version and implementation
- `torch` version
- `transformers` version
- `numpy`, `pandas`, and `scikit-learn` versions
- operating system and machine type
- system RAM when available
- CUDA availability
- CUDA version when available
- GPU name when available
- GPU VRAM when available
- Apple MPS availability when relevant
- selected device or `auto` device resolution
- data root
- output root
- persistent storage location
- Hugging Face cache location
- `HF_HOME` and `TRANSFORMERS_CACHE` setting names if used
- install command
- full Phase 3C command
- seed
- warnings and limitations

The committed public-safe report records the presence and structure of these
fields, but it intentionally does not include private absolute paths, executable
paths, hostnames, or credential values.

## Storage Layout

Use placeholder-style paths in committed docs. Actual local paths may be written
only to ignored local run artifacts.

| Purpose | Colab placeholder | Local placeholder | Commit? |
| --- | --- | --- | --- |
| repository clone | `/content/perturb-LM` | `$PROJECT_ROOT` | source/docs/tests only |
| persistent run root | `/content/drive/MyDrive/perturb-lm/phase3c` | `$PROJECT_ROOT` | no generated outputs |
| data root | `/content/drive/.../data/raw/jump_pilot` | `$PROJECT_ROOT/data/raw/jump_pilot` | no |
| output root | `/content/drive/.../outputs/phase3c` | `$PROJECT_ROOT/outputs/phase3c` | no |
| Hugging Face cache | `/content/drive/.../cache/huggingface` | `$PROJECT_ROOT/.cache/huggingface` | no |
| model files | cache-managed local files | `$PROJECT_ROOT/models` or `.cache` | no |

`data/`, `outputs/`, `results/`, `models/`, `.cache/`, `.env`, and `.venv/`
must remain local or ignored.

## CPU Fallback

CPU execution is supported by the frozen encoder wrapper and is appropriate for
synthetic tests, command validation, and very small dry runs. CPU runs may be too
slow for the full embedding pass. If the final run falls back to CPU, record that
fallback explicitly and do not imply that GPU acceleration was used.

## Credential And Data Safety

- Never print or write actual Hugging Face token values.
- Do not commit `.env`, notebook secrets, shell history, or credential caches.
- Keep `HF_HOME`, `TRANSFORMERS_CACHE`, data roots, outputs, embeddings, model
  weights, fitted projections, indexes, and generated reports under local ignored
  locations.
- Do not commit raw profile tables, row-level results, embeddings, parquet files,
  NumPy arrays, model files, or private absolute local paths.
- Do not add generated JSON reports to Git unless they are tiny synthetic
  fixtures intended for tests.

## Pre-Run Checks

Before any real Phase 3C run that will generate embeddings or evaluation
artifacts, record:

```bash
git branch --show-current
git rev-parse HEAD
git status --short
python scripts/print_environment_report.py
```

Generated artifacts from that future run must stay under ignored local paths.
