# Guide-support audit closeout and scientific review

2026-10-20. Related issues: [#30](https://github.com/siamakenna/perturb-LM/issues/30)
and [#52](https://github.com/siamakenna/perturb-LM/issues/52).
**Metadata audit completed; next experiment PROPOSED_NOT_APPROVED.**
This is safe aggregate evidence, not model validation or scored retrieval.

## Recommendation

**Modify the proposed next step to an untrained, profile-only cross-guide
concordance diagnostic, conditional on identity and preprocessing review.**
Metadata capacity supports developing that design. Scoring remains blocked:
source strings and sequence inequality do not establish independent biological
guides, stable gene identities, efficacy or culture independence. Prefer the
[proposed protocol](PHASE5_CROSS_GUIDE_CONCORDANCE_PROTOCOL.md) over a trained
retrieval model for this immediate question.

## Confirmed capacity and units

The preserved census verifies 12/12 profile-file hashes, 11/11 source-file hashes
and the complete 4,524-row original mapping, with no row or field discrepancies.
The selected four matched U2OS/Cas9 CRISPR plates contain 1,536 physical wells:
1,040 noncontrol, 480 labeled control and 16 missing-label wells. Noncontrol
metadata span 247 reagent IDs, 247 syntactically valid sequences and 130 source
gene strings. Observed noncontrol sequences have length 20; their targeting and
biological independence have not been independently reviewed.

Every ordered assignment has 260 query wells, a full 260-well/247-reagent gallery
and 520 noncontrol wells on the other two plates. No-positive queries remain in
the denominator. Raw and training-supported support coincide on these data.

| Spatial mask | Endpoint | Supported queries / 260 | Reagents / sequences | Source gene strings | No-positive queries |
| --- | --- | ---: | ---: | ---: | ---: |
| Different coordinate | A: exact reagent | 26 (10.00%) | 13 / 13 | 13 | 234 |
| Different coordinate | B: provisional different sequence | 234 (90.00%) | 234 / 234 | 117 | 26 |
| Different row AND column | A: exact reagent | 22 (8.46%) | 11 / 11 | 11 | 238 |
| Different row AND column | B: provisional different sequence | 180 (69.23%) | 180 / 180 | 90 | 80 |

All 12 assignments have those counts. They reuse four physical plates; they are
not 12 independent experiments. A and B have **zero intersection of supported
query wells, reagent IDs and source gene strings**, under either mask. This is
an observed property, not a consequence of the endpoint definitions. Comparing
A and B scores as a paired relevance-only intervention would change populations.

For stricter B across all assignments, deduplicating physical wells leaves:

| Unit | Inspected count | Interpretation |
| --- | ---: | --- |
| Physical wells | 720 | 180 per physical query plate; repeated gallery roles do not add wells |
| Source reagent IDs | 180 | Distinct library identifiers, not certified independent interventions |
| Distinct normalized DNA strings | 180 | Metadata-distinct sequences; independent guide identity not established |
| Source gene strings awaiting stable mapping | 90 | Candidate annotation groups; actual unique stable-gene count remains unknown |
| Independently reviewed stable gene IDs | 0 supplied | Review absent; does not mean zero biological genes |
| Physical plates | 4 | Independent culture preparations remain unresolved |

## Implementation review

- Exact reagent equality is distinct from B's different reagent **and** different
  normalized sequence **and** exact source-gene-string equality. Case-normalized
  equal sequences under distinct IDs are rejected for B. DNA syntax is only
  nonempty A/C/G/T; it does not establish a valid targeting guide.
- Duplicate source reagent keys, conflicting selected local/source gene or
  sequence fields, contradictory conditions and duplicate physical wells block
  the census. Checks do not trust `resolved=true` alone. Missing/ambiguous gene or
  sequence annotations cannot create B support; such gallery rows remain visible.
- Gene checks preserve source strings and reject token ambiguity, not biological
  ambiguity. They do not resolve aliases, species, assembly, stable IDs, target
  loci, reverse-complement identity, clone aliases or off-target effects.
- The shared Phase 5.1 validator and canonical-well/plate-role functions preserve
  physical identities. Both endpoints use identical condition/spatial masks and
  full noncontrol galleries. Reported candidate and positive histograms include
  zero-support queries; pair counts are separate from unique wells.
- Training support is **reagent-ID presence**, not an unseen-guide test. In the
  real census all query reagents/sequences are exposed on training plates. An
  alias ID can expose an exact sequence even when the query ID is absent; new
  synthetic review coverage demonstrates that distinction. A future trained
  design needs canonical guide/sequence groups across all roles.
- Deterministic counts and aggregation passed prior fixtures. Fresh review also
  tests source aliases, sequence case aliases, equal candidate masks and an
  invented case where A/B populations overlap. Real disjointness was checked
  from records, never inferred from the marginal aggregate counts alone.

## Provenance and preservation

Audit implementation Git SHA: `60af90117836b5b563f7ca8113a8a285b0956a46`.
Merged-main base: `c0518710d38adb17a21e150db45b0388a503b030`.
Original source revision: `56845c7d4dc322652952783d91dae0ffef47829f`
in the [CPJUMP1 source repository](https://github.com/jump-cellpainting/2024_Chandrasekaran_NatureMethods_CPJUMP1/tree/56845c7d4dc322652952783d91dae0ffef47829f).

| Preserved artifact | SHA-256 |
| --- | --- |
| Inspected `metadata-support-summary.json` | `6482d029871bbbb1934dd288ba0a35ae865c16c5c0ee1375de421eac4f15b2e3` |
| Original census before inspection | `0e5f18e5fa64ce7fb85263610fd85576808e5280129011dbc8f809b4ac9f61e1` |
| Original profile manifest | `5773f804c7475404651db4a0bbafc4c5f93f96d10b13add317f58335b7f93366` |
| Original source provenance manifest | `726ac169b3047b90a891fb9f7e64c40f482375575d2ee651de014e4bd154bfff` |
| Independent inspection implementation | `55650057ce89abfa2a672dae390b4433bbb03ee170d6b49f3fa384498a2580f2` |

The CLI produced the original census. A separately retained, hashed stdlib
inspection verified all 48 assignment/mask/endpoint combinations and added
overlap/unique-support evidence and a revised proposed next step. Those added
inspection fields are not claimed as a direct CLI output. Comparing both saved
artifacts confirms their census and verification payloads are identical; only
the next-step text changed among pre-existing keys. The full original mapping
has a current digest but no retroactive frozen signature; exact raw-row/source
reproduction is the substantive completeness check.

At closeout, all 17 prior guide-audit output files are ignored and untracked,
including `repository-context.json`. A fresh ignored directory retains the
preservation inventory, copied inspector and current validation; it does not
overwrite the original output. No output files or private input paths belong in
the reviewed Git diff. Historical profiles, mappings, manifests, metrics and
benchmark contracts remain unchanged.

Prior audit validation: 84 tests and 41 subtests passed. Closeout validation is
recorded separately below; no historical test result is relabeled as a fresh run.

## GitHub and security status

The closeout uses local branch `codex/phase5-guide-support-audit`, initially clean
at the audit SHA above. Its only new changes are four safe aggregate documents
and five synthetic review cases in the existing test file. The original project
remains on `feature/benchmark-v2-scikit` at
`3884195d233daebf7f7ab82def690a6c8fc66572` with its pre-existing untracked
`.firecrawl/`, `output/` and `tmp/`. The original Phase 5 worktree remains clean
on `science/phase5-cpjump1-audit` at
`0ee3a11d6e27975df79798ff6f67bfba08258074`. Neither checkout was reset or updated.

Read-only GitHub checks on 2026-10-20 found main still at the base SHA above.
GitHub could not resolve the local audit SHA (API returned "No commit found").
The local audit is not represented as pushed or covered by remote CI.

| PR | Inspected head | State | CodeQL gate |
| --- | --- | --- | --- |
| [#77](https://github.com/siamakenna/perturb-LM/pull/77) | `600a38f7161079d8a11bafc0dc4073feadf1f632` | Open draft, unmerged | [Failure](https://github.com/siamakenna/perturb-LM/runs/116544631569) |
| [#83](https://github.com/siamakenna/perturb-LM/pull/83) | `a15704ba31beee6cec0a35fc9b7f0e1016335afb` | Open draft, unmerged | [Failure](https://github.com/siamakenna/perturb-LM/runs/118777250085) |

Their other successful checks do not clear the failing CodeQL gate. Neither
proposal's code was executed or incorporated; no alert was dismissed or merge
performed. This metadata contribution remains separate from Batch8 security
remediation. No remote CI result exists for the new local closeout changes.

## Remaining blockers

1. Independent guide identity, canonical aliases/sequence equivalence, target
   mapping and stable gene IDs have not been reviewed; final eligible genes may
   differ from the 90 source annotation groups.
2. Meaningful independent experimental units, guide efficacy/intervention
   compatibility, WGA suitability and different-gene reference exclusions need
   Claire's review. Distinct source labels are not verified biological negatives.
3. Exact normalization and feature-selection fit populations/parameters for the
   selected artifact bytes remain unknown. Approve a limited conditional
   interpretation or obtain separately authorized suitable inputs; a new scaler
   cannot undo upstream information exposure.
4. The proposed effect, weighting, structural completeness, minimum meaningful
   units and conditional uncertainty plan need explicit scientific decisions.
5. Public source sharing is a separate action. PR77/83 remain security-blocked;
   those gates do not supply scientific approval or permission to score here.

See the [collaborator checklist](PHASE5_CROSS_GUIDE_REVIEW_CHECKLIST.md) and
[figure specifications](PHASE5_GUIDE_SUPPORT_FIGURE_SPECIFICATIONS.md).

## Fresh closeout validation

- **89 targeted tests passed, zero failed/skipped; 41 subtests passed.** This is
  the existing 84-test selection plus five new synthetic review cases, not 89
  newly written tests. The historical 84/41 record remains preserved.
- Ruff lint and formatting checks passed for the audited Python files and
  revised test file. Standalone public-copy consistency and Git whitespace
  checks passed. The full optional-dependency suite was not run in this closeout.
- Re-executed the preserved independent metadata inspector from a copy in a fresh
  ignored directory: all 48 combinations agree; all 12 profile and 11 source
  hashes still match. This recomputes metadata support only, not real scores.
- Both original census/inspected-summary digests match. All 17 original output
  files, the four original mapping/manifest bindings and five audit implementation
  hashes remain unchanged. No full census or predictive-query workflow was rerun.
- No generated context, original data or outputs are tracked or staged. The
  closeout changes consist of safe aggregate documents and synthetic tests;
  production audit code remains identical to `60af901`.

Reproduce the scoped synthetic checks using the existing core environment:

```bash
PYTHONPATH=src python -m pytest -q tests/test_phase5_guide_support.py \
  tests/test_phase5_1_rotations.py tests/test_phase5_audits.py
ruff check src/perturb_lm/audits/guide_support.py \
  src/perturb_lm/audits/support_inputs.py src/perturb_lm/audits/rotations.py \
  scripts/audit_phase5_guide_support.py tests/test_phase5_guide_support.py
ruff format --check src/perturb_lm/audits/guide_support.py \
  src/perturb_lm/audits/support_inputs.py src/perturb_lm/audits/rotations.py \
  scripts/audit_phase5_guide_support.py tests/test_phase5_guide_support.py
python scripts/check_public_copy_consistency.py
git diff --check
```

Scientific decisions remain unchecked. No scored experiment, trained model,
pretrained inference, data/model download, Biowulf workload, Batch8 rerun, remote
publication, alert dismissal, merge or release occurred during closeout.
