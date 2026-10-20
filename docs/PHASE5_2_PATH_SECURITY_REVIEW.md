# Phase 5.2 Batch8 path and integrity review

Status: proposed corrective implementation, 20 October 2026. Linked review:
PR #77; scientific scope remains bounded by issues #30 and #52. This document
does not adjudicate GitHub alerts or approve a new scientific experiment.

## Evidence and threat model

The authenticated operator export at `2026-10-20T15:54:44.306598+00:00`
binds PR #77 to `600a38f7161079d8a11bafc0dc4073feadf1f632` and main to
`c0518710d38adb17a21e150db45b0388a503b030`. All 118 export-manifest entries
verified. Its Python SARIF contains 28 open, high-severity `py/path-injection`
findings (#105–#132), all on that PR head. Checks were 12 successful, one
CodeQL failure and one skipped. These are exported observations, not a fresh
authenticated request from the authoring environment.

The flagged paths originate in local operator CLI arguments, rather than a
shown remotely accessible service. Existing fixed filenames, input hashes and
fresh-directory checks are useful. They did not enforce the wrapper's stated
boundary: the Python entry points could create a fresh output directory outside
the ignored repository output tree, and recorded pointers could resolve outside
the work root. An invented-data reproduction confirmed the former behavior
without fetching metadata or reading private profile values. The findings
therefore warrant changes; they are neither blanket false positives nor proof
of a demonstrated remote exploit.

| Original source | Exported alert numbers | Corrective scope |
|---|---|---|
| `control_utils.py` | 105–114 | Bound input snapshots, work-root/output validation, exclusive download and artifact writes |
| `prepare.py` | 118–121, 129–132 | Bound pointers and fixed inputs, recheck immutable sources before plan completion |
| `pilot.py` | 115–117, 122–128 | Confine plans/results, parse verified plan/cohort snapshots, enforce profile pins, publish completion last |

## Corrective behavior

`path_contract.py` makes the existing trusted operator-owned work root explicit.
Inputs and pointer destinations remain inside it. Result directories must be
fresh children of its existing Git-ignored `repo/outputs` tree, must not overlap
inputs, and must not contain tracked files. Wrapper run directories receive the
same checks before logs are opened. This policy also applies to direct Python
entry-point calls; `control_utils.py` now requires `--work-root`.

Internal symlinks, nonregular files, oversize inputs, escaping/malformed pointers,
existing outputs and unsafe nested destinations fail closed. Operating-system
ancestor aliases such as macOS `/var` resolving to `/private/var` are accepted.
Regular-file reads are bounded and checked on the opened descriptor; new files
are created exclusively with private permissions. The fixed public metadata
download writes through an exclusively opened descriptor and validates cached
bytes against the pinned Git blob before publishing the final file.

The scoring entry point parses the same plan/cohort byte snapshots that it
verifies. Profile hashes remain pinned to the reviewed constants, with checks
before loading and after evaluation. Checksum verification of other artifacts
precedes publication of the completion summary. A failure leaves incomplete
artifacts and a failure marker, rather than a successful completion summary.
This is not a transaction across the complete output directory.

The trust boundary assumes an operator-owned work tree and implementation.
Checks reduce accidental redirection and file substitution; they do not claim
protection against a same-user process deliberately racing ancestor-directory
renames or repeatedly replacing and restoring files. No new remote exposure or
privileged execution model is introduced.

## Historical results and validation

The completed Batch8 pilot remains bound to the original code at
`600a38f7161079d8a11bafc0dc4073feadf1f632`, its original approved plan and
summary hashes. Future path-hardening code has different implementation hashes
and cannot reuse the old plan as an approval. This change does not request a
rerun. `engine.py`, `query_info.py`, cohort selection, scientific constants and
the Parquet projection/scoring mathematics remain unchanged.

Focused synthetic tests exercise output containment, ignored/tracked paths,
internal links, bounded regular-file reads, pointer escapes, macOS ancestor
aliases, exclusive writes, immutable-input changes, approval/cohort binding,
profile substitution and failed-completion handling. The CI workflow explicitly
discovers the archived pilot suite and installs its figure dependency; these
tests were outside the repository's default `tests/` discovery path.

Exact local test counts and dependency limitations are recorded in the appended
20 October entry in `scripts/phase5_2_batch8_pilot/VALIDATION.txt`. The two real
Parquet IO tests require PyArrow. Invented-data tests and mocked Parquet loading
are not validation against private Batch8 profile values or a substitute for
GitHub CI.

## Outstanding security disposition

The revised source has not been scanned by CodeQL in the authoring environment.
After a separately reviewed draft fix branch is pushed, bind every new check
and SARIF result to its exact head SHA. Inspect remaining traces individually;
custom path helpers are not guaranteed to be recognized as sanitizers. Do not
dismiss alerts, suppress rules, alter workflow permissions or bypass a failing
check to make the PR mergeable. No alert disposition or repository setting was
changed by this review. PR #77 remains unmerged.
