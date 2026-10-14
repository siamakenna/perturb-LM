# Phase 5.1 reproducibility and validation

2026-10-14. **PROPOSED_NOT_APPROVED.** Related issues: #30 and #52.
This is metadata planning only. No model is fitted, no query is encoded, and no
retrieval score or inference job is produced.

## Evidence and fresh validation

Development starts from the supplied, verified Git bundle at
`0ee3a11d6e27975df79798ff6f67bfba08258074`. The transfer's remote-head record agrees.
Direct GitHub access is unavailable in this environment; remote publication
requires the separate authenticated handoff. A local commit is not remote sync.

| Check | Fresh result |
| --- | --- |
| New rotation unit/integration tests | 20 passed, zero failed, zero skipped using stdlib unittest on Python 3.12.14 |
| Synthetic CLI from an unrelated working directory | Passed as part of those 20 tests; private ignored outputs and evidence labels verified |
| Public-copy consistency script | Passed |
| Python compilation | Passed for the three new Python files |
| Local wheel build, no network/dependency installation | Passed; wheel contains the exact planner module; version remains 0.2.0a1, not released |
| Whitespace and source preservation | Diff check passed; pre-existing tracked files unchanged from the audit commit |
| Ruff and existing pytest regressions | Not run here: tools unavailable; attempted dependency installation found no available distribution in this environment. Required in the publication handoff |
| Full suite and actual local-profile analytics | Not run; original profiles/private mapping are absent and this environment lacks optional dependencies |

These counts do not incorporate historical Phase 5 or Phase 4 validation. No new
performance or power claim follows from passing synthetic tests. Development
runtime used pandas 2.2.3 and NumPy 2.3.5; it is not the pinned Phase 3B environment.
The handoff runs focused regressions in the operator's existing environment and
records its versions separately. No frozen contracts, metrics, identifier guards
or source profile files are modified by this change.

## Reproduce the synthetic plan

From this repository, with its base Python dependencies available:

```bash
PYTHONPATH=src python3 -m unittest discover \
  -s tests -p test_phase5_1_rotations.py -v

PYTHONPATH=src python3 scripts/plan_phase5_1_rotations.py \
  --synthetic-fixture \
  --min-train-groups 3 \
  --min-evaluable-groups 2 \
  --upstream-normalization-scope source_batch_global \
  --out outputs/phase5_1/rotations-synthetic
```

Choose a new output directory if it already exists. Thresholds 3 and 2 are
**synthetic test parameters**, not recommendations for real experiments. The
fixture contains 24 invented records with `SYNTH_` record/reagent/gene values and
the four public plate IDs needed to exercise the fixed proposed stratum.

Expected synthetic result: 12 candidate and 12 design-eligible rotations, each
with four non-control query rows, three evaluable rows from two reagent IDs, and
a four-row gallery containing three reagent IDs. One fixed-coordinate reagent
has no surviving positive but remains in the gallery. Two evaluable reagents
share one invented gene, exercising the distinction between reagent and gene
counts. Every rotation still has `execution_allowed=false`.

Outputs are `rotation-plan.json`, `rotation-manifest_PRIVATE.csv`, and
`SHA256SUMS`. Their directory must be new, inside this checkout's Git-ignored
`outputs/`; a symlink escaping that root is rejected. Outputs use private file
permissions. The summary records input and implementation hashes, the source
Git commit and whether input was explicitly selected as the synthetic fixture.
It does not certify a real mapping's source provenance merely by hashing it.

## Real metadata plan: original data-holding machine only

The actual `local_mapping_PRIVATE.csv` is required. Do not recreate its rows from
the reported 13 IDs / 104-row summary or substitute the two image sites. Before
planning, compare every unchanged historical profile file against the completed
audit's `profile_manifest.json` (relative path, SHA-256, rows and feature schema),
and verify the audit source snapshot/provenance. Keep the extra timepoint outside
the frozen selection. Reconcile any mismatch before generating a new plan.

Use the full audited mapping, not a prefiltered recoverable-ID table. Proposed
minimum group thresholds must be supplied deliberately and recorded for review;
the software cannot select scientific minima or determine statistical power.
After setting the variables below to actual local values, run from the checkout:

```bash
bash <<'BASH'
set -euo pipefail
: "${P51_MAPPING:?Set P51_MAPPING to the existing private audit mapping CSV}"
: "${P51_MIN_TRAIN:?Set an explicit proposed minimum training reagent count}"
: "${P51_MIN_EVALUABLE:?Set an explicit proposed minimum evaluable reagent count}"
: "${P51_OUT:?Set a fresh path under this checkout's outputs/phase5_1/}"

PYTHONPATH=src python3 scripts/plan_phase5_1_rotations.py \
  --mapping "$P51_MAPPING" \
  --min-train-groups "$P51_MIN_TRAIN" \
  --min-evaluable-groups "$P51_MIN_EVALUABLE" \
  --upstream-normalization-scope unknown \
  --out "$P51_OUT"
BASH
```

Use `source_batch_global` only when provenance supports that scope; neither
supported label permits inductive claims or enables execution. No flag accepts
an unsupported assertion of train-only normalization. Treatment-heldout and
gene-heldout requests fail closed because their group assignments have not been
implemented or reviewed.

## Interpret the counts before deciding

`design_eligible` means only that the metadata and operator-supplied count
thresholds passed for the proposed seen-treatment design. It does not establish
independent cultures, valid query encoding, approved uncertainty or permission
to score. The four stated physical plates must all be represented; both assigned
training plates must contribute usable non-control rows.

`candidate_count` and `positive_count` are profile-row counts after coordinate
filtering. Their `*_reagent_count` counterparts count distinct candidate IDs and
positive IDs, respectively, after the same mask. The positive reagent count is
zero or one. These support the proposed existing M0 treatment-gallery rule of
averaging surviving scores by reagent after filtering; the planner computes no
scores. Counts of distinct nonblank gene annotation strings are labeled
`gene_annotation_groups`, not certified independent genes or cultures. Resolve
missing, ambiguous or multi-gene annotations before clustered uncertainty.

The private manifest retains selected rows in all assigned roles, including
control/missing-label exclusions and non-evaluable queries. Out-of-stratum rows
are counted in the aggregate summary; their identities remain in the input
mapping. Ambiguous selected mappings stop the run rather than disappear from
the eligibility ledger. Inspect coverage and blockers before considering the
[reviewer checklist](PHASE5_1_REVIEWER_CHECKLIST.md).
