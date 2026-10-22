# Phase 5.2 GitHub continuation

2026-10-22. **PROPOSED_NOT_APPROVED.** Issues: #30, #52.
This is the next-device entry point. The branch contains all required audit,
identity/design helpers, tests, aggregate evidence and scientific documentation;
the old chat and a ZIP/export are not dependencies.

## Repository checkpoint

- Repository: https://github.com/siamakenna/perturb-LM
- Branch: `science/phase5-2-cross-guide-readiness-20261022T144928Z`
- Verified base/main: `c0518710d38adb17a21e150db45b0388a503b030`.
- The isolated branch starts at that base; old unpublished ancestors are not pushed.
- Draft PR: [#84](https://github.com/siamakenna/perturb-LM/pull/84).
- Verified published implementation HEAD/checkpoint:
  `aa0f5a57c9028551f628f45a2833864e1fadc7cc`. Local HEAD equaled the exact
  `git ls-remote` branch SHA after the first push. Subsequent commits add
  this documentation receipt and the scoped manifest-path security follow-up.
  The current authoritative head is PR84 `headRefOid`,
  which must equal the remote branch and local checkout. The PR body records the
  final verified publication head without requiring a commit to contain its own SHA.

## Published file groups

- Audit modules: `guide_support.py`, `support_inputs.py`, `rotations.py`,
  `gene_identity.py` and `cross_guide_design.py` under `src/perturb_lm/audits/`.
- CLIs: `scripts/audit_phase5_guide_support.py` and
  `scripts/prepare_phase5_cross_guide_readiness.py`.
- Synthetic tests: `tests/test_phase5_guide_support.py` and
  `tests/test_phase5_cross_guide_readiness.py`, using existing main fixtures and
  planner/audit/guard tests. No private fixtures or new dependencies are required.
- Scientific docs: guide-support feasibility/closeout, concordance protocol and
  review checklist, figure specifications, historical handoff, readiness and this
  continuation document.
- Five JSON records in `docs/evidence/phase5_2/`: sanitized census receipt,
  nomenclature aggregate, HGNC pins, public-source pins and actual validation.

## Read first

Read AGENTS.md, [claims ladder](CLAIMS_LADDER.md),
[evaluation protocol](EVALUATION_PROTOCOL.md), and
[Phase 3C contract](PHASE3C_TEXT_PROFILE_ALIGNMENT.md), followed by
[Phase 5.2 readiness](PHASE5_2_CROSS_GUIDE_READINESS.md), the
[proposed concordance protocol](PHASE5_CROSS_GUIDE_CONCORDANCE_PROTOCOL.md), and
[decision checklist](PHASE5_CROSS_GUIDE_REVIEW_CHECKLIST.md).
The original cohort/Phase 5.1 documents remain historical/proposed records.

Completed: the full preserved metadata census, its receipt validation, offline
HGNC nomenclature matching and synthetic design-contract tests. Proposed:
biological guide/target approval, artifact-specific fit interpretation, inference
units, uncertainty and any real concordance calculation. Computational HGNC
matches do not complete biological review. The narrower profile-only diagnostic
is the smallest proposed next experiment; it needs no trained model, text query
or encoder. The production F10 guard and WGA status stay unchanged.

## Fresh checkout and core test setup

Run this in a directory where a new sibling checkout is appropriate. The unique
destination preserves every existing checkout and local change. Use Python 3.11
(project supports 3.10–3.12); no model/pixel extras are needed for these tests.

```sh
destination="$(mktemp -d "$PWD/perturb-lm-phase5.XXXXXX")"
git clone --single-branch \
  --branch science/phase5-2-cross-guide-readiness-20261022T144928Z \
  https://github.com/siamakenna/perturb-LM.git "$destination"
cd "$destination"
git status --short
git rev-parse HEAD
git ls-remote origin refs/heads/science/phase5-2-cross-guide-readiness-20261022T144928Z
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest -q tests/test_phase5_cross_guide_readiness.py \
  tests/test_phase5_guide_support.py tests/test_phase5_1_rotations.py \
  tests/test_phase5_audits.py tests/test_query_generation.py \
  tests/test_public_copy_consistency.py
python scripts/check_public_copy_consistency.py
```

Require commands to succeed before proceeding and compare the full local/remote
SHAs. This setup downloads software dependencies only; it does not retrieve
research profiles, weights, private ledgers or run scientific workloads. Remote
CI uses additional optional dependencies; a local core test pass is not a full
optional-dependency suite or a security approval.

## Original-Mac-only command: offline identity preparation

The existing original census must not be rerun merely to recreate a handoff.
`scripts/prepare_phase5_cross_guide_readiness.py` reads only metadata/reference
inputs and verifies the preserved census receipt hash. It does not open profiles.
The private original mapping, source provenance/annotation, inspected census
receipt, and already downloaded pinned HGNC reference bytes are required.
The GitHub aggregate projection is not a substitute for that original receipt.
Set these local variables to their actual retained locations before using:

```sh
P5_CODE_ROOT="$PWD"
(
cd "$P5_INPUT_ANCHOR"
PYTHONPATH="$P5_CODE_ROOT/src" "$P5_PYTHON" \
  "$P5_CODE_ROOT/scripts/prepare_phase5_cross_guide_readiness.py" \
  --audit-root "$P5_AUDIT_ROOT" \
  --census-summary "$P5_ORIGINAL_CENSUS_RECEIPT" \
  --census-root "$P5_CENSUS_RECEIPT_ROOT" \
  --expected-summary-sha256 bf193358fdb31d06f68fdd7d937310787c7c686829b6f19b54c2251e4f6ba81a \
  --hgnc-approved "$P5_HGNC_APPROVED" --hgnc-withdrawn "$P5_HGNC_WITHDRAWN" \
  --reference-manifest "$P5_CODE_ROOT/docs/evidence/phase5_2/hgnc-reference.json" \
  --reference-root "$P5_REFERENCE_INPUT_ROOT" \
  --out "$P5_CODE_ROOT/outputs/phase5_2_identity_FRESH"
)
```

Before this example, set `P5_PYTHON` to the absolute path of the validated Python
environment and `P5_INPUT_ANCHOR` to a trusted common ancestor of the receipt,
reference manifest and both HGNC TSVs. Start in the repository so `P5_CODE_ROOT`
captures its absolute location. The subshell changes only the input anchor;
output stays beneath the repository's ignored `outputs/` directory.

`P5_CENSUS_RECEIPT_ROOT` contains the original receipt.
`P5_REFERENCE_INPUT_ROOT` contains both HGNC TSVs and the reference manifest;
it can equal the anchor if those files occupy separate subdirectories. Both
root flags default to the invocation directory and can only narrow access
beneath it. They cannot authorize access outside it. Descendant symlinks and
parent traversal are rejected, while aliases above the invocation directory,
including macOS `/var`, remain supported. JSON is limited to 4 MiB and each
HGNC TSV to 32 MiB; the preserved approved reference exceeds the JSON limit.
Each parsed value and its SHA-256 bind the same bounded byte snapshot.
These input checks do not rerun or revise historical results.

This preparation is already completed; rerun only when an independent review or
an authorized identity revision requires it, using a fresh ignored directory.
Never pass a private cohort list to HGNC/GPP/genome web services. Whole public
reference acquisition, if needed, must use the pinned manifest and verify hashes;
missing generations/different bytes must be reported rather than silently updated.

## Remaining scientific and execution gates

Claire: intended target/canonical guide identity, secondary symbol candidates,
locus/orientation and sequence equivalence, efficacy, acceptable reference
relationships and independent culture units. Adam: original input bindings,
artifact-specific normalization/selection fit receipts or bounded interpretation,
spatial/gallery rules, repeated-reference dependence, weights and future scorer.
Makenna: scientific scope, estimand, complete-support cohort, meaningful units,
uncertainty, intended claims and written execution authorization. No collaborator
review has been requested or asserted complete.

No real-data cosine/retrieval calculation, predictive text, model inference,
training, new profile/model download, private-data transfer or Biowulf workload
is authorized by this publication. No scoring runner is provided here. A future
scorer needs separate authorization, protocol review and synthetic validation.
Do not repeat Batch8, dismiss security alerts, merge, release, deploy or contact
collaborators under this handoff. PR77/83 remain separate unmerged proposals;
their code was neither incorporated nor executed.

Initial local validation passed **119 tests and 41 subtests**. A publication
CodeQL path-handling finding prompted the narrowly scoped manifest-path
hardening documented in the readiness report and two additional regression
tests. The follow-up passed **121 tests and 41 subtests**; the validation JSON records
both runs separately. Full optional-dependency tests are left to CI.
GitHub reported 14 default-branch dependency alerts on push (2 critical, 5 high,
7 moderate). They were not suppressed or adjudicated here; see the repository
[dependency alerts](https://github.com/siamakenna/perturb-LM/security/dependabot).
Inspect the draft PR checks for the current head before any further publication
or merge decision; passing local tests does not clear these separate concerns.

The next task that needs only GitHub is independent review of the nomenclature
precedence rules, candidate exclusions, complete-support weighting and tests,
followed by a concrete proposed decision/implementation plan. Private biological
review and original-byte provenance require the original data holder. Record
those blockers without substituting synthetic evidence for scientific approval.
