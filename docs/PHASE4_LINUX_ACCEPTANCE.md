# Phase 4 Linux acceptance runner

This utility runs existing tests against a clean, explicitly selected checkout.
It is not a GitHub Actions runner and does not replace required hosted checks.
It does not add pretrained comparators, change model backends, publish a
release, or execute a production dataset.

## Scope

Stages run in order: the three pixel test modules (including the existing
installed-wheel test), the comparator text-encoder tests, then the repository
suite with no command-line file exclusions. Counts overlap: do not sum stages.
The runner clears external pytest selection settings and pytest `addopts` so a
prior `-k`, `-m`, or `--ignore` option cannot quietly narrow this acceptance run.
Code in pytest hooks and markers can still skip tests; all skips are reported.
The image and comparator stages reject skipped tests; the repository stage
explicitly reports PASS_WITH_SKIPS when appropriate.

The intended environment is Python 3.11/3.12 on Linux with
`.[dev,phase3c,pixel]`, `build`, and any build-time dependencies requested by the
existing installed-package test. Use the exact selected source checkout.
All code must be reviewed and limited to synthetic/fixture-based tests.
Offline environment flags prevent normal Hugging Face downloads but are not a
network sandbox; do not add network-dependent model/dataset tests to this run.

## Usage

Keep the runner outside the tested checkout if it is not yet committed:

```bash
python /path/to/run_phase4_acceptance.py \
  --repo /path/to/clean/checkout \
  --out /path/to/new/results
```

The default timeout is 1,800 seconds per stage. A timeout terminates the stage's
process group. No empty or all-skipped test run counts as successful. The run
stops at the first failed stage or source mutation and records REVIEW_REQUIRED.
If a Slurm allocation is killed abruptly, the summary can remain INCOMPLETE;
never treat that as completion. Use a fresh output directory for a new attempt.

`summary.json` contains only selected versions, commit/hash, counts, statuses,
and timing. Review it before sharing. Raw `*.private.log` and `*.private.xml`
files can contain paths and tracebacks: retain them in approved private storage.
Do not upload environment dumps, credentials, raw data, model weights, or logs.
A report's source_commit is the application revision tested, not necessarily the
later commit that adds this utility. The runner's own bytes have a separate hash.

## Slurm

Set ACCEPT_REPO, ACCEPT_ENV, ACCEPT_OUT, and ACCEPT_DRIVER, and optionally
ACCEPT_MODULE. Request one job using `phase4_acceptance.sbatch`; this is not the
old four-stage embedding worker and does not accept a model-comparison array.
Dependency installation belongs in a compute allocation before submission.

## Validation interpretation

These are software/integration checks. A passing mock-based comparator test is
not pretrained-checkpoint inference or a biological result. A Linux pass is not
an untested claim about macOS/Windows or all supported Python versions.
The existing historical benchmark and production-readiness gates are unchanged.
