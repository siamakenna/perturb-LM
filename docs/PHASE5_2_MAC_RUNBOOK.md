# Phase 5.2: transfer and execution on the original Mac

> Status update, 2026-10-15: the repaired 18-test layout suite and the bounded
> public Batch8 pilot have completed on the operator's Mac. This document
> retains its earlier scope and validation history. Read the
> [current pilot record](PHASE5_2_BATCH8_PILOT_RECORD.md) before repeating
> setup or interpreting work previously listed as pending. Scientific
> manuscript approval and biological validation remain outstanding.

2026-10-14. This runbook applies reviewed source additions and runs metadata
audits. It does not submit jobs, fit models, score retrieval, merge, or publish.
Related issues #30 and #52. Scientific status remains **PROPOSED_NOT_APPROVED**.

## 1. Inspect the transfer

Extract `perturb-lm-phase5-2-transfer.zip` into a fresh folder. Inside its
`perturb-lm-phase5-2-transfer` directory, read `README.txt` and run:

```bash
shasum -a 256 -c SHA256SUMS
```

The package contains an additions-only `overlay/`, `phase5-2.patch`, the original
snapshot's file-hash inventory, scientific documents, synthetic fixtures/tests,
validation records and transfer helpers. No private research files are required
for the public compound-layout audit. The helpers themselves are not proposed
repository changes; the overlay is the proposed source diff.

Set the following two paths in your terminal. The first is the extracted package;
the second must be an existing Perturb-LM checkout on this Mac. Use the actual
paths, preserving quotes around spaces.

```bash
export P52_PACKAGE="/actual/path/to/perturb-lm-phase5-2-transfer"
export P52_EXISTING="/actual/path/to/existing/perturb-LM"
```

## 2. Create an isolated branch at the supplied base and apply additions

Use an existing Python 3.10–3.12 interpreter. The new metadata utility and transfer
helpers use the standard library only. There is no need to repeat the image
environment installation. If `python3` is not the intended interpreter, export
`P52_PYTHON` with its full path before this block.

```bash
bash <<'BASH'
set -euo pipefail
umask 077
export PATH="$HOME/.local/bin:$PATH"
export GH_HOST=github.com
: "${P52_PACKAGE:?Set the extracted package path first}"
: "${P52_EXISTING:?Set the existing checkout path first}"
P52_PYTHON="${P52_PYTHON:-python3}"
P52_BASE=c0518710d38adb17a21e150db45b0388a503b030

(cd "$P52_PACKAGE" && shasum -a 256 -c SHA256SUMS)
"$P52_PYTHON" -c 'import sys; assert (3,10) <= sys.version_info[:2] < (3,13), sys.version'

git -C "$P52_EXISTING" remote get-url origin
git -C "$P52_EXISTING" fetch origin main
git -C "$P52_EXISTING" cat-file -e "$P52_BASE^{commit}"
git -C "$P52_EXISTING" merge-base --is-ancestor "$P52_BASE" origin/main

P52_WORK="$(mktemp -d "$HOME/Downloads/perturb-lm-phase52.XXXXXX")"
P52_BRANCH="science/phase5-2-design-$(date -u +%Y%m%dT%H%M%SZ)"
git -C "$P52_EXISTING" worktree add -b "$P52_BRANCH" "$P52_WORK/repo" "$P52_BASE"

"$P52_PYTHON" "$P52_PACKAGE/transfer-tools/verify_and_apply.py" --repo "$P52_WORK/repo"
"$P52_PYTHON" "$P52_PACKAGE/transfer-tools/verify_and_apply.py" --repo "$P52_WORK/repo" --apply

printf '%s\n' "$P52_WORK" > "$HOME/Downloads/perturb-lm-phase52-work-location.txt"
git -C "$P52_WORK/repo" status --short
printf '\nWorking folder: %s\nBranch: %s\n' "$P52_WORK" "$P52_BRANCH"
BASH
```

The helper requires the exact supplied commit, a clean checkout and all 374
baseline file hashes. It copies new files only. A mismatch is evidence to review;
do not reset an existing worktree, edit the expected SHA, or force the patch.
It does not stage, commit or push. Creating this worktree preserves the original
audit worktree and its ignored private outputs.

## 3. Run the new synthetic checks and review the additions

```bash
bash <<'BASH'
set -euo pipefail
umask 077
P52_PYTHON="${P52_PYTHON:-python3}"
P52_WORK="$(cat "$HOME/Downloads/perturb-lm-phase52-work-location.txt")"
cd "$P52_WORK/repo"
export PYTHONPATH="$PWD/src"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
unset PYTHONHOME

"$P52_PYTHON" -m unittest discover -s tests -p test_phase5_2_layouts.py -v
mkdir -p outputs
P52_RUN="$(mktemp -d "$PWD/outputs/phase52-synthetic.XXXXXX")"
"$P52_PYTHON" scripts/audit_phase5_2_layouts.py \
  --synthetic-fixture --out "$P52_RUN/audit"
(cd "$P52_RUN/audit" && shasum -a 256 -c SHA256SUMS)
"$P52_PYTHON" scripts/check_public_copy_consistency.py
git diff --check
git status --short
BASH
```

The fresh audit output is a nonexistent child; do not precreate it.
All counts from `--synthetic-fixture` are invented test data, not JUMP findings.

In the established project environment, also run the existing rotation tests:

```bash
(
  cd "$(cat "$HOME/Downloads/perturb-lm-phase52-work-location.txt")/repo"
  PYTHONPATH=src "${P52_PYTHON:-python3}" -m unittest discover \
    -s tests -p test_phase5_1_rotations.py -v
)
```

That test suite needs the existing core dependencies and a real Git checkout.
Do not change its output guard to make an unpacked archive pass. If Ruff is
already installed, run its configured lint/format checks on the three new Python
files. Ruff and the pytest/full suite were not available in the development
environment, so they are not represented as passed in this transfer.

## 4. Acquire only four small public design tables, then audit them

This requires working `gh` access on the Mac. It is read-only public metadata
retrieval; no private files are uploaded. Resolve the upstream commit once,
then fetch the four allowlisted TSVs at that immutable revision. The helper
requires inline file content, verifies Git blob identity and SHA-256, and limits
each file to 1 MiB. It does not follow LFS or download profiles/images.

```bash
bash <<'BASH'
set -euo pipefail
umask 077
export PATH="$HOME/.local/bin:$PATH"
export GH_HOST=github.com
: "${P52_PACKAGE:?Set the extracted package path first}"
P52_PYTHON="${P52_PYTHON:-python3}"
P52_WORK="$(cat "$HOME/Downloads/perturb-lm-phase52-work-location.txt")"
cd "$P52_WORK/repo"
export PYTHONPATH="$PWD/src"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
unset PYTHONHOME
mkdir -p outputs
P52_RUN="$(mktemp -d "$PWD/outputs/phase52-public-layouts.XXXXXX")"

P52_TARGET_REV="$(gh api --hostname github.com \
  repos/jump-cellpainting/JUMP-Target/commits/master --jq .sha)"
printf 'Pinned public Target revision: %s\n' "$P52_TARGET_REV"

"$P52_PYTHON" "$P52_PACKAGE/transfer-tools/fetch_target_metadata.py" \
  --revision "$P52_TARGET_REV" --out "$P52_RUN/source"

"$P52_PYTHON" scripts/audit_phase5_2_layouts.py \
  --metadata-dir "$P52_RUN/source" \
  --provenance "$P52_RUN/source/metadata-provenance.json" \
  --out "$P52_RUN/audit"

(cd "$P52_RUN/audit" && shasum -a 256 -c SHA256SUMS)
printf '\nRead this aggregate report: %s/audit/summary.json\n' "$P52_RUN"
BASH
```

Live retrieval was not executed here. If a source annotation conflict stops the
audit, retain the inputs/receipt and inspect the conflict; do not remove a row to
force a desired overlap count. The input hashes bind the downloaded bytes, not
their biological correctness. Standardized-key matches need structure/stock
review. A partial map must not be reported as a complete 384-well crosswalk.

## 5. Turn design matches into a measured-cohort proposal

The four-file audit does **not** join measured plates. Adam should next pin the
production metadata repository, inspect its small plate table and schema, and
identify source_4 TARGET1/TARGET2 candidates. A plate-type label alone does not
establish matched conditions or local profile availability. The measurement
manifest must retain source, batch, physical plate, acquisition, well, JCP ID,
sample/structure provenance, controls, dose, duration, cell context, selection or
polybrene treatment, imaging/pipeline and culture lineage. Missing fields remain
unknown. Do not download the entire well table or profile collection blindly;
first inspect object sizes and available bounded partitions.

Produce a layout × batch × condition contingency table. Prioritize a condition
where both layouts are observed with compatible processing. If layout and batch
are inseparable, state that limit explicitly. No scored experiment follows
automatically from a nonzero match count.

On the original data-holding Mac, separately execute the provenance/coverage
work specified in [local metadata specification](PHASE5_2_LOCAL_METADATA_SPEC.md).
The existing Phase 5.1 planner is reused for its original exact-reagent question;
the same-gene assessment is a new proposed endpoint. Its synthetic acceptance
cases in that specification are not yet implemented or executed.

## 6. Review and return only the needed evidence

Review the scientific plan and query/preprocessing specification with the
responsibilities assigned there. Source application and successful metadata
tests do not approve relevance definitions, thresholds, fitting or publication.

Useful return items are test summaries, the public layout aggregate summary and
non-sensitive descriptions of unresolved provenance. Keep original profiles,
private mappings, guide sequences, row-level plans and machine paths local.
There is no need to transfer private NIH data to this conversation.

For a later source PR, review and stage the explicit additions after validation.
Use a normal push and verify the remote head on the authenticated Mac. This
runbook intentionally ends before a commit/push because this request asks for a
transfer package and scientific development, not publication. No remote action
has been performed on the user's behalf.
