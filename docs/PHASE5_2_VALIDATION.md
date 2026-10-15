# Phase 5.2 validation record

> Status update, 2026-10-15: the repaired 18-test layout suite and the bounded
> public Batch8 pilot have completed on the operator's Mac. This document
> retains its earlier scope and validation history. Read the
> [current pilot record](PHASE5_2_BATCH8_PILOT_RECORD.md) before repeating
> setup or interpreting work previously listed as pending. Scientific
> manuscript approval and biological validation remain outstanding.

2026-10-14. Related issues #30 and #52. This record concerns the supplied archive
and additive development in this conversation, not a new GitHub revision or a
real-data experiment. Scientific status remains **PROPOSED_NOT_APPROVED**.

## Checks actually executed

| Check | Result and scope |
|---|---|
| Supplied ZIP integrity and inventory | Passed CRC inspection; 374 files inventoried with SHA-256 |
| Preservation of supplied source | All 374 original file hashes unchanged; changes are additions only |
| New layout audit tests | **17 passed**, standard-library `unittest`, including CLI, provenance, partial maps, ambiguity and deterministic output checks |
| Transfer helper tests | **21 passed**, offline; Git/GitHub interactions are mocked where needed |
| Existing Phase 5.1 rotation tests | **20 passed** in an isolated temporary Git fixture reconstructed from the original archive |
| Existing public copy consistency script | Passed |

The Python interpreter was CPython 3.12.14 on Linux. The existing rotation tests
used available pandas 2.2.3 and NumPy 2.3.5. This is an observed test environment,
not a proposed replacement for the project's constrained environment.

Executed commands:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p test_phase5_2_layouts.py -v
python3 transfer-tools/test_transfer_tools.py
PYTHONPATH=src python3 -m unittest discover -s tests -p test_phase5_1_rotations.py -v
python3 scripts/check_public_copy_consistency.py
```

The first rotation-suite attempt against the bare source archive had 18 passes,
one failure and one error: two tests depend on Git output-ignore checks. The
unchanged suite subsequently passed all 20 tests in the temporary Git fixture.
That local fixture commit is not upstream history and does not independently
verify the user-supplied commit. The original planner's guard was not weakened.

The transfer package includes the test logs and a separate package-verification
receipt. A successful patch-application check against the reconstructed archive
establishes compatibility with those bytes, not compatibility with a remotely
verified Git tree. The Mac helper separately requires the exact supplied main
commit and every original file hash before copying any new files.

## Limits and pending validation

- No full pytest suite, Ruff run, package matrix or macOS execution was performed
  here; pytest and Ruff were not available in this environment.
- The public fetch helper was tested offline. Live GitHub API retrieval and a
  complete four-table JUMP crosswalk remain to run on the original Mac.
- No private profiles, guide mapping or real cohort rotation outputs were
  available for execution. Public browser inspection is not a hashed dataset
  snapshot or a measured-cohort analysis.
- The same-gene/different-guide specification and annotation workflow are
  proposed work; their acceptance examples are not implemented tests.
- No pretrained inference, fitted model, retrieval score, statistical power
  estimate, biological validation, remote push, PR, merge or release occurred.

Use [the Mac runbook](PHASE5_2_MAC_RUNBOOK.md) for source reconciliation and the
next bounded metadata audit. Retain missing or contradictory biological evidence
as unresolved; passing software tests does not approve a scientific contract.
