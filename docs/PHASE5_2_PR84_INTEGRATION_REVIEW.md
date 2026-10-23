# PR84 integration and scientific review handoff

2026-10-22. Issues #30, #52; [PR84](https://github.com/siamakenna/perturb-LM/pull/84).
**ENGINEERING_READY for independent review; SCIENTIFIC_REVIEW_PENDING;
COMPUTE_AUTHORIZATION_PENDING.** These are separate decisions. PR84 stays draft
and unmerged; this document grants no scientific execution permission.

## Verified checkpoints and preservation

- Main: `ef7e74ac2f76b6c111d0f8bac2a9f2ff0e7ef6f7`.
- Successful PR84 source checkpoint: `44ba331e6e5b4f73468d1632d2c79c4695c7b215`.
- GitHub test merge: `3e33a2a5582dd7ffebbe2ecd040880cad283badf`, with exactly
  those main/PR parents; tree `4ec89d0f998a04838575e71f9caa31fbfd8cda22`.
- The isolated local merge produced that exact tree before this documentation
  update. No source, scientific definition or dependency repair was necessary.
- Local integration branch: `codex/pr84-main-integration-20261022`; publication
  fast-forwards the existing PR branch after validation, without force/reset.
- The original project, audit/closeout worktrees and the earlier local publication
  branch at `0ff10b3f7c1f319ece0864c57111f349eab4307d` were preserved.

No `REVIEW_PR84.zip` was found in the checked Downloads, Desktop, Documents or
Codex attachment locations. Authenticated GitHub records were used instead.
The successful source checkpoint's 14 checks were complete: 13 successful,
including CodeQL and Python 3.10/3.11/3.12 package installs, and the manual real
profile smoke skipped. This evidence is preserved, not inferred from the old
incomplete ZIP reports. New-head CI after integration is a separate observation;
consult the PR checks, not an older failure table, for current status.

Only source integration, synthetic tests, packaging and review documentation were
performed. No census, nomenclature lookup, Batch8/MOA analysis, numeric-profile
parsing or morphology scoring was repeated. Private data and original scientific
artifacts remain on their owning Mac. No collaborators were contacted.

## Compatibility assessment

Main now includes PR77 (squash merge `21d2da843f4492602a62efe1995c969585d915ec`)
and dependency/workflow updates. The integration keeps setup-python v7, the
deploy-pages update, Torch `<2.15`, PyArrow 25.0.1 and main's NumPy 2.2.6 minimum
choice. PR84's already completed SciPy 1.15.3 / scikit-image 0.25.2 repair survives
the automatic merge unchanged. No new pin, packaging repair or CodeQL fix was
made in this integration review.

The merged modules serve distinct purposes: `layouts.py` compares compound layout
designs; `guide_support.py` counts measured CRISPR metadata capacity;
`gene_identity.py` performs nomenclature matching; `cross_guide_design.py` tests
proposed relation/weight contracts. Shared role enumeration/canonical wells still
come from `rotations.py`; its planner rules and synthetic thresholds are unchanged.
`json_inputs.py` supplies the already reviewed bounded descriptor-relative reads.
No duplicate planner, gene resolver or scored runner was introduced.

The older Phase 5.2/Batch8 documents describe other datasets and historical
proposals/results. They do not establish CPJUMP1 cross-guide concordance. In
particular, standardized-parent compound layout matching, exact-reagent recovery,
gene-aware text sensitivity and same-gene/different-guide concordance remain
different questions. Historical documents and results were retained, with this
handoff supplying the current interpretation rather than rewriting their dates.

## Validation executed for this integration

The [aggregate integration receipt](evidence/phase5_2/integration-review.json)
records exact commands, source/test-merge bindings and safe hashes. Targeted
metadata, identity, gallery/weighting, JSON/path-security, layout, release-diagnostic,
query-guard and public-copy regressions passed **165 tests and 69 subtests**, with
no failures/skips. Public-copy and whitespace checks passed. A fresh ignored
build-only environment built the wheel and sdist; eight audit modules imported
from an isolated installed wheel, and wheel audit-source bytes matched this tree.
No private output/data members were found in either archive. Local Python was
3.12.5; the full optional suite and 3.10/3.11 installation matrices were not
repeated locally. The prior successful remote matrix is separate evidence.

No manual runtime/test/dependency change was required: only the already tested
main integration and current review/continuation documentation are being added.
Security checks were existing synthetic regressions and preserved remote CodeQL,
not a new local CodeQL scan or repository-wide security sign-off.

## PR83 disposition: revise separately, do not close as duplicate

[PR83](https://github.com/siamakenna/perturb-LM/pull/83) remains open at
`a15704ba31beee6cec0a35fc9b7f0e1016335afb`, with CodeQL failing and changes
requested at the inspected checkpoint. Its two commits beyond the original PR77
source `600a38f7161079d8a11bafc0dc4073feadf1f632` are:

| Commit | Unique corrective intent still absent from main |
| --- | --- |
| `9b9513af32e7dfe58e1512f911ca27eac93f786d` | Batch8 work-root/pointer confinement; fresh ignored output policy for direct Python entry points; bounded regular-file reads and exclusive writes; verified plan/cohort/profile bindings; completion published last; wrapper approval tied to implementation bytes; explicit synthetic pilot test discovery in CI |
| `a15704ba31beee6cec0a35fc9b7f0e1016335afb` | Parse and hash a single bounded layout-provenance snapshot, with leaf-symlink/nonregular/oversize/substitution tests |

Comparing the two-commit delta against current main confirms that the relevant
pilot and layout-CLI source files in main still equal the pre-security PR77
versions. The security delta touches 14 files and is not subsumed by PR84's
CRISPR JSON reader. In particular, the merged layout CLI still parses provenance
and later reopens it for hashing. Batch8 direct-entry output/root and pointer
contracts remain a distinct concern. PR77 was squash-merged, so a raw ancestry
range can still list its original commit; that is not evidence the two unique
security changes have landed.

Recommendation: retain PR83, revise/rebase it against current main in a separate
security review, preserve both corrective intents and their tests, and update
its stale statement that PR77 is unmerged. Retain current setup-python/workflow
and dependency updates while reconciling its added pilot test discovery. Do not
blindly substitute PR84's current-directory anchor for Batch8's work-root policy;
review the intended trust boundary and wrapper invocation first. The documented
same-owner concurrent-ancestor race limits still require explicit adjudication.
Do not silently drop unique fixes, close PR83 as duplicate, dismiss alerts or
merge its patch into PR84. No PR83 code was executed or incorporated here.
No pilot mathematics, historical plan or completed result should be rerun to
validate these path changes. A changed implementation needs a new approval if
real execution is later authorized.

## Preserved scientific evidence

The [aggregate receipt](evidence/phase5_2/metadata-support-summary.json) preserves
verification of 12 original profiles, 11 source files and the complete 4,524-row
mapping. Strict B metadata support is 180/260 queries across 90 provisional
source-string groups per assignment; all 130 source gene strings match exact
approved HGNC symbols. Three have secondary historical/alias candidates requiring
intended-target review. Four physical plates underlie 12 overlapping assignments.
There are no newly measured cross-guide morphology scores. Nomenclature resolution
is not independent biological target/guide approval, and the metadata counts are
not counts of independent cultures. Exact-reagent support remains separate.

## Decisions to record before an experiment

| Owner | Specific evidence/decision still required |
| --- | --- |
| Claire | Canonical guide/clone aliases and sequence equivalence/orientation; intended target and assembly/locus evidence, including secondary HGNC candidates; editing efficacy/off-target limitations; culture/biological independence; permissible same-gene and reference relationships. Freeze inclusion/exclusion decisions in a private reviewed ledger with evidence, reviewer/date and digest. |
| Adam | Bind the exact profile artifacts to normalization/feature-selection fit record populations, software/configuration and dataset provenance, or explicitly bound the interpretation; review split/guide exposure, physical-well identity, full-gallery integrity, zero-support coverage, gene/guide-pair/plate-pair weights and repeated-reference dependence. Four plates/12 roles cannot imply independent holdouts. |
| Makenna | Choose the estimand and finite-cohort scope; approve strict primary/sensitivity populations, statistical unit, minimum meaningful units and uncertainty strategy; decide intended claims and give explicit scientific authorization tied to the exact protocol/ledger/configuration hashes. |

No decision is prefilled as approved. WGA remains retained, the production F10
guard is unchanged, upstream fitting scope is not certified by matching feature
headers, and synthetic 3/2 thresholds are not study settings.

The smallest proposed next experiment is the
[untrained profile-only cross-guide concordance diagnostic](PHASE5_CROSS_GUIDE_CONCORDANCE_PROTOCOL.md):
strict different-plate/row/column as primary; coordinate-only sensitivity;
same reviewed gene with independently reviewed different guides; exclude same
canonical reagent/guide and equivalent sequence entries; keep the full gallery
and no-positive/reference queries in coverage. Different-gene comparisons are
unlabeled references, not validated negatives. Balance within guide pairs and
physical plate comparisons, then genes; do not bootstrap wells or rotations as
independent cultures. No unseen-guide/gene claim or label-renaming null is valid.

Execution gates remain: frozen reviewed identity/relevance ledger; agreed units,
population/masks, weighting and uncertainty; accepted artifact-fit interpretation;
separately reviewed and synthetic-tested scorer; written scientific authorization;
and separate compute/private-data staging authorization. No real scoring, training,
predictive query generation, dataset/model download, private transfer or Biowulf
job follows from ENGINEERING_READY.

## Continue on either Mac

On a Mac with an existing repository, preserve its checkout and changes:

```sh
git status --short
git fetch origin refs/heads/science/phase5-2-cross-guide-readiness-20261022T144928Z:refs/remotes/origin/pr84-reviewed
review_dir="$(mktemp -d "${TMPDIR:-/tmp}/perturb-lm-pr84.XXXXXX")"
git worktree add --detach "$review_dir" refs/remotes/origin/pr84-reviewed
cd "$review_dir"
git rev-parse HEAD
```

On a Mac without a checkout, use a new destination:

```sh
review_dir="$(mktemp -d "$PWD/perturb-lm-pr84.XXXXXX")"
git clone --single-branch --branch science/phase5-2-cross-guide-readiness-20261022T144928Z \
  https://github.com/siamakenna/perturb-LM.git "$review_dir"
cd "$review_dir"
git status --short
git rev-parse HEAD
```

On both Macs, compare HEAD with the PR head and exact remote ref; read AGENTS.md
and this handoff before setup. Use the setup/test commands in
[the continuation document](PHASE5_2_CONTINUATION.md). No reset, clean, automatic
stash or private-file transfer is needed. The source-only reviewer Mac can review
contracts, tests, aggregate evidence, packaging and PR83's security diff entirely
from GitHub. It must not invent missing private records.

On the data-holding Mac, retain original profiles, private mappings/identity
ledgers and historical outputs in place. Do not repeat completed analyses to
populate a new worktree. A later independently requested metadata review must
respect the bounded readers' invocation-directory anchor: root flags only narrow
that anchor. Use an explicitly trusted common invocation directory and an absolute
script/PYTHONPATH when existing inputs span checkouts; do not move private inputs
or choose a filesystem-wide anchor just to bypass confinement. Obtain a new
execution decision before any feature/scoring step. No Biowulf continuation or
new scientific result is authorized by this handoff.
