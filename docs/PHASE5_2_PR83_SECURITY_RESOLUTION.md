# PR83 security revision and independent-review checkpoint

23 October 2026; PRs [#83](https://github.com/siamakenna/perturb-LM/pull/83)
and [#84](https://github.com/siamakenna/perturb-LM/pull/84); issues #30, #52.

This is a security engineering revision. It grants no scientific or compute
approval, and does not ask to repeat the completed Batch8 pilot.

## Verified state and preservation

- Current main: `ef7e74ac2f76b6c111d0f8bac2a9f2ff0e7ef6f7`.
- Original PR83 head: `a15704ba31beee6cec0a35fc9b7f0e1016335afb`.
- PR84 remains unchanged at `97aa27e78aa3fb52f1628bbd046ff6ad64ac822d`;
  all 14 checks completed: 13 successful and manual real-profile smoke skipped.
  It remains a draft, unmerged, with independent review required.
- PR83 had 18 review threads, 17 unresolved; alert 134 was already resolved.
  Adam's changes-requested review remains active. None were dismissed/resolved
  by this work; engineering dispositions are evidence for renewed review.

Current main is integrated through an additive merge, preserving PR83's original
commits and review history. All nine add/add conflicts arose from PR77's squash
merge: the conflicting main files were byte-identical to the original PR77
source. PR83's security versions were retained; current main's dependency and
workflow updates were retained. The effective diff against main contains security
code, synthetic regressions and review documentation, not duplicated PR77 science.
Existing checkouts, dirty files, branches and private/frozen artifacts remain in
place. No private input census, historical pilot or morphology scoring was run.

## Findings and dispositions

The [individual disposition ledger](evidence/pr83-security-dispositions.json)
records every unresolved thread, original source location, GitHub alert link,
source-to-sink trace endpoints, original mitigation/gap and revised behavior.
Its original Python SARIF is bound to analysis 1990394690 and PR83's exact head.

| Alerts | Original assessment | Correction or evidence |
| --- | --- | --- |
| 125 | Confirmed directory-creation boundary gap | Recheck directories now use the verified ignored-output policy and descriptor-relative creation; recheck evidence is retained rather than removed by a stale pathname. |
| 133 | Confirmed scratch-unlink boundary gap | Remove the scratch name relative to its held output-parent descriptor. |
| 135, 136 | Confirmed parent-path read gap | No-follow directory traversal, descriptor-relative leaf stat/open, full inode/size/mtime/ctime comparison, and named-leaf revalidation. |
| 137, 138 | Confirmed exclusive-write parent gap | O_EXCL/O_NOFOLLOW still apply, now to one leaf relative to a held parent. An original-source invented fixture reproduced a write outside the validated outputs parent during a swap; the new regression prevents redirection. |
| 139–146 | Sufficiently mitigated static metadata probes under the trusted-local-operator model; their checks were not concurrency capabilities | Remove the pathname link loop; perform directory/file type and preservation probes descriptor-relatively and independently secure the later operation. Separate trace instances remain separate ledger entries. |
| 147, 148 | Confirmed mkdir/streamed-open parent gaps | Create directories and streamed-download files relative to held parents; private modes, exclusive writes and receipt verification remain. |
| 149 | Sufficiently mitigated static local-operator manifest read; additional parent hardening warranted | Retain one bounded manifest snapshot for parsing/hash, reuse the no-follow descriptor primitive, and record that helper's implementation hash. The manifest parent is its operator-selected anchor; no Batch8 work-root or PR84 invocation-root policy is substituted. |

The concrete parent-swap reproductions stress conditions beyond the old stated
quiescent-workspace assumption; they establish a boundary gap, not evidence of a
remote exploit. Metadata-only probes are not classified as arbitrary payload
reads merely because they depend on intended operator arguments. No finding is
blanket-dismissed as a false positive and no CodeQL rule/model/suppression or
permission setting was changed.

## Retained protections and limits

Batch8 still requires an explicit trusted work root; pointers and inputs remain
confined to it. New results must be fresh, Git-ignored descendants of its existing
`repo/outputs`, free of tracked files and input overlap. Static internal links,
unsafe file types, oversize files, malformed/escaping pointers and existing outputs
fail closed. Operator-root/OS ancestor aliases remain accepted. Directory and
file modes remain 0700/0600. Platforms without required no-follow descriptor
support fail closed.

The shared helper lives with the archived pilot source so standalone archived
kits keep their security implementation and plan code hashes. The layout CLI
uses only that filesystem helper, not pilot execution code. A source-only layout
archive must include `scripts/phase5_2_batch8_pilot/path_contract.py`; the archive
fixture checks this dependency. This is independent of PR84's specialized JSON
reader and its invocation-directory trust policy.

Plans/cohorts are parsed from the verified bytes. Numeric Parquet projection,
if separately authorized in future, receives the exact bounded profile snapshot
whose digest was checked, rather than reopening a mutable path. Completion stays
last; input pins, code-bound approvals and wrapper implementation agreement remain.
`engine.py`, `query_info.py`, `layouts.py`, cohort-selection AST and module
scientific constants match main. Original accepted outputs and historical code
hashes are preserved. Changed code cannot reuse a historical plan approval.

The trusted operator still owns the root, interpreter, Git configuration and
implementation. Held descriptors prevent symlink redirection; they cannot prevent
an equally privileged owner moving an already opened directory, altering memory,
creating hard links or racing the entire shell wrapper. This is not hostile-owner
isolation, a transaction, a multiuser service or a repository-wide security sign-off.
The old shell wrapper's runtime/dependency setup remains a trusted local operation.
No real execution is authorized to test these limits.

## Validation and fresh CI

Local checks use invented fixtures only. The Batch8 suite passed 82 tests, including
six new adversarial tests for parent swaps during read/write/mkdir, restored-mtime
rewrites, component-prefix sibling escapes and invalid work roots. The existing Parquet IO tests use
invented tables; the scoring-path tests use invented matrices/mocked profile IO.
An existing local Matplotlib installation supplied figure-test dependencies; no
download or modification of the research environment was performed. Earlier local
attempts without Matplotlib and intermediate fixture failures were retained in
ignored logs, corrected, and are not counted as passing validation.

Layout/provenance, rotation, public-copy and release-contract checks, wheel/sdist
builds, isolated archive imports, Bash syntax, focused Ruff and whitespace checks
are recorded in the exact-head validation receipt/PR description. Local validation
is not a fresh CodeQL scan. After publication, inspect the new head's CI and Python
SARIF; retain remaining findings with exact locations and proposed corrections.
Prior successful checks must not be used to certify this revision.

The first fresh scan on `ea925bc3fc4f86215b3d19f5f67e7f7e97b56838`
(Python analysis 2010507686) retained original alerts 139/140 at
`path_contract.py:127` (`work_root.resolve`) and `:130` (`work_root.is_dir`).
Both are intentional local-operator root metadata probes, not new remote payload
flows. They are now replaced by descriptor-based root verification, with a new
missing/non-directory-root regression. No suppressions or dismissals were used.
The other 15 original unresolved findings were absent from that fresh SARIF.
The follow-up head requires its own scan; the failed first scan remains evidence.

Current main's minimum package cohort pins NumPy 2.2.6 with SciPy 1.12.0 and
scikit-image 0.22.0. PR84 already contains the separate cohort repair. This security
revision does not duplicate that repair. The first fresh minimum-install job
failed at `wheel-base` with exit 1
([job](https://github.com/siamakenna/perturb-LM/actions/runs/39899294069/job/120236912914)).
Its uploaded summary reports `CalledProcessError`; the old validator does not
upload or print the underlying private pip log, so a fresh resolver message is
unavailable. The constraint conflict is a known likely cause, not newly observed
resolver text. Relevant locations are `configs/package-minimum.txt:2–6` and
`scripts/validate_release_artifacts.py:112–140`. Reconcile using reviewed PR84/main
integration, which also supplies packaging diagnostics, and rerun the exact head;
do not weaken checks or duplicate its dependency repair here.

## PR84 independent scientific review

PR84's validated engineering covers descriptive metadata support, nomenclature,
full-gallery/unsupported-query accounting and synthetic contract checks. Its
support counts are candidate capacity: they contain no measured morphology
concordance, independent guide-efficacy evidence, biological relevance approval
or proof of independent cultures. Four plates underlie 12 overlapping assignments.
Synthetic 3/2 thresholds specify fixtures, not biological sample size or power.

Claire must review canonical guides/targets, sequence equivalence, efficacy,
independence and relevance. Adam must bind preprocessing fit populations to exact
artifacts and review dataset/split provenance, gallery integrity and weighting.
Makenna must approve the estimand, scope, statistical units, uncertainty strategy
and final scientific protocol. No such approval is recorded here.

The proposed next diagnostic remains untrained profile-only cross-guide
concordance with reviewed identities and prespecified masks, full galleries,
coverage, weighting and uncertainty. Before execution: freeze the reviewed private
identity/relevance ledger; accept artifact-specific preprocessing interpretation;
approve the statistical protocol; separately review/synthetic-test a scorer;
record scientific authorization; and obtain separate compute/private-data staging
authorization. No scoring, inference, training, new data transfer or Biowulf job
is authorized by an engineering check.

## Recommended sequence

1. Review PR83's individual dispositions, current diff, new-head CodeQL and tests;
   retain Adam's requested-changes review until explicit renewed review.
2. Independently review PR84 at its unchanged green head. A human may choose to
   merge it after engineering review; this grants no scientific/compute approval.
3. If PR83 packaging is blocked by the already repaired PR84 cohort, integrate the
   newly reviewed main additively into PR83 and rerun all required checks on that
   exact head. Do not copy the repair into a competing security implementation.
4. A human may merge PR83 only after its exact head satisfies required checks and
   security review is explicitly approved. Reconcile overlapping-main changes
   and reassess findings; an outdated thread is not an approval.
5. Complete scientific decisions and obtain separate execution authorization before
   implementing or running the proposed real-profile experiment.

No PR is merged, review dismissed, reviewer contacted or approval inferred by
this handoff. For either Mac, fetch both heads and create a new detached worktree;
do not reset existing branches or transfer private artifacts. PR84's existing
[integration handoff](https://github.com/siamakenna/perturb-LM/blob/97aa27e78aa3fb52f1628bbd046ff6ad64ac822d/docs/PHASE5_2_PR84_INTEGRATION_REVIEW.md)
continues to describe its separate scientific gates.
