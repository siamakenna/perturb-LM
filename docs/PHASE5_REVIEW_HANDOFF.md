# Phase 5 independent review handoff

Historical October 20 packet. The current GitHub publication and next-device
entry point is [Phase 5.2 continuation](PHASE5_2_CONTINUATION.md). Statements below
about unpublished branches and pending nomenclature describe the October 20
checkpoint; the new nomenclature lookup does not complete biological review.

2026-10-20. Related issues: [#30](https://github.com/siamakenna/perturb-LM/issues/30),
[#52](https://github.com/siamakenna/perturb-LM/issues/52).
**Review package prepared. Diagnostic PROPOSED_NOT_APPROVED and not ready to run.**
No collaborator review, scientific approval or publication authorization is implied.

## Evidence and proposed next step

The October 20 audit implementation is local commit
`60af90117836b5b563f7ca8113a8a285b0956a46`; closeout documentation and synthetic
review tests are in `93c51982c67193ff721053ad8e2b1aae2dcdbf4c`. The preserved
inspected summary has SHA-256
`6482d029871bbbb1934dd288ba0a35ae865c16c5c0ee1375de421eac4f15b2e3`.
The [closeout](PHASE5_GUIDE_SUPPORT_CLOSEOUT.md) contains the full provenance chain.

The stricter metadata-supported cross-guide candidate population contains
**180 reagent IDs, 180 sequence strings, 90 source gene strings and four physical
plates** (720 unique wells). Independently reviewed stable gene and guide
identities have not been supplied; the actual stable-gene count is unknown.
These are candidate relationships, not observed morphological concordance.

Each of 12 overlapping assignments contains 260 query wells and a full 260-well /
247-reagent gallery. Strict cross-guide support is 180/260 queries, compared with
22/260 exact-reagent queries from 11 source gene strings. Their supported
populations are disjoint in this audit. The assignments reuse the same four
plates and do not establish independent cultures or 12 independent replications.
All plates retain the WGA flag and matched U2OS/Cas9 CRISPR 144-hour conditions.

Proposed question: **Do profiles from independently verified different guides
assigned to the same reviewed stable gene show greater concordance than matched
different-gene references after different-plate, different-row AND different-column
filtering?** Different genes may be biologically related; these references are
not verified negatives. Prefer an untrained profile-only diagnostic before a
trained retrieval model, which would add fitting and exact-guide exposure risks.

The [protocol](PHASE5_CROSS_GUIDE_CONCORDANCE_PROTOCOL.md) proposes a gene-balanced
mean contrast: average cross-guide same-gene cosine minus gene-balanced matched
reference cosine, aggregated across guides and six unordered plate pairs. No
scores informed this choice or were computed. Sensitivities are (1) less strict
different-coordinate filtering with common-support coverage and (2) directional /
plate-pair ranges. Conditional gene-cluster uncertainty and minimum meaningful
units need review; no interval over independent cultures is established.

## Collaborator handoff

### Makenna

Decide whether this narrow conditional diagnostic is the manuscript's next
experiment or whether independent/expanded data are needed first. Approve or
revise the primary contrast, complete-support population, two sensitivities,
uncertainty interpretation and intended claims before observing scores. Keep
exact-reagent and cross-guide populations separate. Decide publication and any
future compute/data authorization separately; local tests authorize neither.

### Claire

The **exact 90 candidate source gene groups are identified only in the local
private review packet**, not listed in Git. `candidate-gene-review_PRIVATE.json`
contains 90 pending groups; `candidate-guide-review_PRIVATE.json` links their 180
source reagents to sequence checksums and original mapping record IDs.
`reference-gallery-review_PRIVATE.json` covers the additional 67 gallery reagents
so unreviewed reference labels cannot be treated as known negatives. All review
fields are blank/pending and no full guide sequence was copied into these forms.

Practical workflow on the data-holding machine:

1. Open `review-packet_PRIVATE.json` and verify its source/protocol digests. Resolve
   each record against the unchanged original mapping and CRISPR annotation table
   by reagent ID; inspect raw sequences locally in those original records.
2. Review stable gene namespace/version, species/assembly, aliases and ambiguous
   assignments. Review canonical guide identity, clone/sequence aliases, target
   locus/orientation, intervention compatibility and available efficacy/off-target
   evidence. Unequal strings alone do not prove independent targeting guides.
3. Judge culture independence, meaningful experimental units, WGA suitability and
   acceptable different-gene reference relationships. Preserve unknown labels.
   Do not use morphology scores to settle identity or efficacy questions.
4. Record reviewer/date, decision and independent evidence. Resolve disagreements
   explicitly. Freeze the reviewed ledger and report its digest plus safe aggregate
   inclusion counts; do not paste private names, rows or sequences into GitHub.

The local packet is an extraction/index of preserved metadata, not a new audit,
biological validation or completed collaborator review. Access or transfer to
another machine requires an appropriate separate sharing decision.

### Adam

Verify raw profile/source manifest bindings and mapping provenance against the
preserved audit; distinguish the original census from the hashed later overlap
inspection. Reproduce metadata counts from reviewed code when independent review
requires it, without interpreting them as scores. Establish exact upstream
normalization/feature-selection fit populations, versions and parameters, or
state why only a limited conditional/transductive interpretation is supportable.

Review canonical wells, physical identity, condition matching, full-gallery and
zero-support accounting, exact-guide/sequence alias exclusion, aggregation weights,
reference reuse and repeated-plate dependence. The primary diagnostic has no
training. A later trained design needs canonical guide/sequence closure across
splits; absent reagent IDs alone do not prove an unseen guide. Preserve the F10
guard and frozen benchmarks. Review any future scoring implementation and its
synthetic tests against the approved protocol before it touches real features.

## Execution gates — all decisions remain pending

| Gate | Required evidence / decision | Owner | Current state |
| --- | --- | --- | --- |
| Stable gene and guide identity | Reviewed stable IDs, canonical aliases, independent targeting evidence and ambiguous-label decisions, including reference gallery | Claire; Adam checks binding | Pending; private index prepared, no identities approved |
| Observation and biological units | Culture provenance and explicit distinction among genes, guides, wells, sites and plates | Claire | Culture independence unresolved |
| Relationship contract | Prespecified reviewed same-gene/different-guide relations and matched reference/unknown-label handling | Claire + Makenna | Proposed, not approved |
| Gallery and masks | Full base gallery; canonical guide exclusions; different physical plate, row AND column; matched conditions; zero-positive/reference ledger | Adam + Claire | Metadata rules reviewed; scientific use pending |
| Effect and weighting | Fixed descriptive contrast, complete-support rule and equal gene/guide/plate-pair weights | Makenna + Adam | Proposed, no scores |
| Uncertainty and minimum units | Approved conditional unit/interval or explicitly unavailable interval; meaningful group minimum | Claire + Adam | Unresolved; synthetic 3/2 thresholds do not apply |
| Preprocessing interpretation | Exact fitted populations/parameters or explicitly reviewed limited interpretation | Adam + Makenna | Exact fit scope unknown |
| Scoring implementation | Separately authorized, reviewed profile-only implementation with synthetic tests, input binding and frozen configuration | Adam | Not supplied by the metadata auditor; no new scorer built here |
| Scientific execution authorization | Written decision tied to exact protocol revision and reviewed manifest digests | Makenna with scientific reviewers | Absent; no execution authorized |

Do not start scoring until all applicable gates are explicitly resolved. A source
publication decision, passed tests or a review request is not execution approval.
No model training, new profile/model acquisition or Biowulf workload is authorized.

## Proposed public review branch and full inventory

Branch: `codex/phase5-review-handoff`. Intended base: `main`, verified at
`c0518710d38adb17a21e150db45b0388a503b030` on 2026-10-20. The branch preserves
both unpublished local audit/closeout commits; a PR against main therefore needs
the entire inventory below, not only the five-file closeout-parent diff.
Code and scientific text are proposals for independent review, not asserted approved.

| File relative to repository | Review purpose |
| --- | --- |
| `src/perturb_lm/audits/guide_support.py` | Metadata-only exact-reagent and provisional cross-guide counts |
| `src/perturb_lm/audits/support_inputs.py` | Complete preserved-input verification, no feature-value analysis |
| `src/perturb_lm/audits/rotations.py` | Extract shared role/well helpers; preserve existing planner rules |
| `scripts/audit_phase5_guide_support.py` | Local audit CLI with ignored output and provenance records |
| `tests/test_phase5_guide_support.py` | Invented fixtures and 36 metadata/identity review tests |
| `docs/PHASE5_GUIDE_SUPPORT_FEASIBILITY.md` | Auditor behavior and reproducibility |
| `docs/PHASE5_GUIDE_SUPPORT_CLOSEOUT.md` | Safe aggregate findings, validity review and provenance |
| `docs/PHASE5_CROSS_GUIDE_CONCORDANCE_PROTOCOL.md` | Proposed untrained diagnostic; no execution |
| `docs/PHASE5_CROSS_GUIDE_REVIEW_CHECKLIST.md` | Detailed unresolved collaborator decisions |
| `docs/PHASE5_GUIDE_SUPPORT_FIGURE_SPECIFICATIONS.md` | Coverage/spatial-support figure specifications only |
| `docs/PHASE5_REVIEW_HANDOFF.md` | This self-contained packet and execution gates |

No generated contexts, outputs, private review forms, mappings, sequences, profiles,
credentials or absolute local paths are in this inventory. Synthetic sequence
literals in tests are invented examples, not source guide sequences. Aggregate
statistics/provenance references are explicitly separate from biological results.

Current status: main unchanged; PR77/83 are separate unmerged drafts with failing
CodeQL gates. Their branch code is not included or executed here. No alert is
dismissed and no remote CI success is claimed for this unpublished branch.
A locally prepared draft PR description and exact diff inventory await explicit
push/open authorization. Nothing has been pushed or opened by this handoff.

## Preservation and validation

The 17 preserved audit output files retain their original digests and remain
ignored/untracked, including `repository-context.json`. All 383 initially tracked
files were inventoried/scanned; the only path-pattern hit was a pre-existing
synthetic runtime-logging fixture outside this diff. Four pre-existing PNG chart
assets are byte-identical to main and excluded from the proposed PR. No actual
source sequence/reagent or credential-pattern matches occurred in tracked text;
the proposed changed-file scan is clean. This scoped scan is not a universal
secret detector, security sign-off or biological review.

Fresh handoff validation: **89 tests passed, zero failed/skipped; 41 subtests
passed**, using the existing three metadata audit/planner test files. Lint,
formatting, standalone public-copy consistency, link and whitespace checks are
recorded in the ignored handoff evidence. The full optional-dependency suite is
not claimed passing. No census, feature analysis, cosine scoring or proposed
experiment was rerun; only integrity checks and private review-index extraction
were performed.
