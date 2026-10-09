# PR #71 path-boundary security review

Refs [#55](https://github.com/siamakenna/perturb-LM/issues/55) and
[draft PR #71](https://github.com/siamakenna/perturb-LM/pull/71).
This review covers local filesystem behavior, not model or scientific validity.
No alert is dismissed or suppressed by this document.

## Verified scanner provenance

The starting remote branch and PR head were both
`6862e1c4f8b5ca52ec687e7b4f307d8bbbc167a4`. No newer remote work was present.
Authenticated alert access returned **89–103**, all open, rule
`py/path-injection` ("Uncontrolled data used in path expression").
Python analysis **1925516612**, category `/language:python`, used
`refs/pull/71/head` at that exact SHA and reported 15 findings. The prior
analysis **1925507806** at `e8bfeba1c1dc4e4d3a4c422039b36225a8095379`
reported the same count; it is historical evidence, not another 15 findings.

GitHub's separate PR merge ref was
`f127c4cd06a3d0ddda6e13d22ff7ecd3d85dc8e7`, whose parents were base
`a6a385b2dd8389ef61c70111c76612c9e95164e4` and the starting PR head.
Its tree and the PR-head tree were both
`aa7c6a6a6ba295c548bbb93c44ccbb6259beaa18`. Thus this analysis applies to
both application trees even though the commit identities differ. These 15
IDs were absent from the base branch's alert list and their two source files
are additions in this PR. They are new PR findings, not the older main-branch
path findings or an outdated merge-ref result.

The complete SARIF contains **33 code flows**, not only the first flow for
each result. All are transcribed below with repository-relative source
locations at the analyzed starting revision. Raw scanner downloads and test
logs remain outside Git. This document contains only public code locations,
curated findings, and synthetic test evidence.

## Trust boundaries and actual operations

1. **Top-level operator inputs.** CLI selection/settings/NPZ/score paths and
   interactive request paths are supplied by the process operator. They are
   intentional file-access capabilities, not names appended to a fixed server
   directory. They may be external, absolute, relative, or aliased as documented
   for each command. JSON/NPZ contents are still untrusted: schema, sizes,
   numeric values, IDs, and pickle prohibition apply separately. Checksums
   detect changes; they do not authorize access. There is no network request
   handler, privilege elevation, or separately authorized caller in these
   scripts. This assessment would not apply if these commands were exposed
   through a service, privileged job broker, or unreviewed third-party request.
2. **Paths inside an inventory/manifest.** `row.path` and `dataset.metadata_path`
   do not get operator-path authority. Callers canonicalize the chosen data
   root; validators reject absolute/parent-traversing names, resolve the joined
   path, apply `Path.is_relative_to` containment, and require a regular file.
   The **returned canonical path**, not the unchecked string, is hashed/read.
   Resolving a symlink may inspect filesystem metadata outside the root to
   determine its target; an escaping target is rejected before file-content
   reading. A sibling sharing a textual prefix with the root does not pass.
   Existing in-root aliases remain permitted. Native approval paths are also
   resolved and confined to the canonical data root before use.
3. **Output destinations.** An operator chooses a fresh output destination;
   untrusted record IDs and model names never become output filenames. Output
   children have fixed names. Previously, the tool created a directory through
   an alias but reused that alias for later writes. A process able to retarget
   the alias could redirect private output into another existing directory.
   `np.savez_compressed(path, ...)` could also overwrite an intervening file.
   These are demonstrated defects, even though the initial destination was
   operator-selected. The fix pins the existing parent with `resolve(strict=True)`,
   rejects any existing leaf (including dangling symlinks), and uses that
   returned canonical path throughout. Directory creation still fails if the
   leaf appears concurrently; JSON/TSV/NPZ/log files use exclusive creation.
4. **Native launch preparation.** Private request fields are operator-controlled
   configuration, not untrusted inventory rows. They must be absolute, resolve
   outside the checkout, and satisfy native-boundary checks. Resolving an
   output leaf previously hid a dangling output symlink; `.exists()` also
   missed dangling `.working` symlinks. Both now fail before preparation, and
   the outer wrapper rechecks both names with `-e` and `-L` before delegation.
   External manifests remain supported. The selected `bin/python` is still
   made absolute **without resolving its final symlink**, preserving venv
   identity. Launch assignments remain shell-quoted; the generated environment
   file must itself be trusted because the wrapper sources it as shell code.

**Filesystem threat limit:** canonicalization fixes alias retargeting; it is
not an operating-system sandbox or a descriptor-relative race-proof filesystem.
The canonical input trees and output parents must be private, operator-controlled,
and stable while a command runs. A hostile process able to rename/replace
canonical directory components (or another process with the same account's
permissions) is outside this guarantee. Confinement checks plus checksums do
not eliminate such read/open races. Supporting hostile shared directories or
untrusted remote callers would require a separately reviewed capability/descriptor
based I/O design, not an analyzer-only string check. No string-prefix containment,
blanket checkout restriction, scan exclusion, or taint suppression was added.

## Alert-by-alert assessment

Locations below refer to the analyzed starting SHA; `C` means
`scripts/comparator_tools.py`, `L` means `scripts/prepare_native_launch.py`.
Every row uses rule `py/path-injection`. The appendix records all alternate
flows, including launcher request paths flowing into comparator helpers.

| Alert | Source and filesystem operation | Existing protection / evidence | Assessment and proposed disposition |
|---|---|---|---|
| [89](https://github.com/siamakenna/perturb-LM/security/code-scanning/89) C:31 | CLI selection, settings, output inventory, and launcher request → `digest` → binary `open` | Selected input files; output names fixed; before/after hashes. Four traces. | Mixed boundary: direct reads are intended capabilities; output-inventory hashing shared the alias defect. Fix output pinning; retain for collaborator review of remaining intended reads. |
| [90](https://github.com/siamakenna/perturb-LM/security/code-scanning/90) C:38 | CLI selection/settings/request → JSON file `stat` | 16 MiB JSON bound; three traces. No inventory-relative name at these sources. | No demonstrated traversal beyond the explicitly selected file. Propose inapplicable path-traversal classification for this local CLI contract, subject to collaborator review. |
| [91](https://github.com/siamakenna/perturb-LM/security/code-scanning/91) C:40 | Same three input sources → JSON `read_text` | JSON/schema validation; operator chooses the complete pathname. | Same intended-read boundary as 90. Review the explicit local-capability rationale; do not assume JSON contents are trusted. |
| [92](https://github.com/siamakenna/perturb-LM/security/code-scanning/92) C:44 | Output CLI paths → inventory/summary/completion JSON; make-request output → exclusive `open` | `open('x')` prevents leaf overwrite, but four traces reuse potentially retargetable parent aliases. | Genuine redirect defect demonstrated. Pin output parent and use returned canonical paths, including request output before prompting. Remaining arbitrary destination selection is intentional and needs reviewer adjudication. |
| [93](https://github.com/siamakenna/perturb-LM/security/code-scanning/93) C:50 | Four commands' `--out` → output `exists` check | Existing-output rejection before `mkdir`; no untrusted output child name. | Shared output-root lifecycle with 92/94/101. Pin parent and explicitly reject symlink leaves. This metadata check alone is not an arbitrary write. Review residual operator-capability flow. |
| [94](https://github.com/siamakenna/perturb-LM/security/code-scanning/94) C:54 | Four commands' `--out` → `mkdir` | Exclusive directory creation, existing parent required, mode 0700. | Creation was exclusive, but subsequent uses were not pinned. Fix lifecycle across every caller; retain scanner finding until collaborator review. |
| [95](https://github.com/siamakenna/perturb-LM/security/code-scanning/95) C:99 | CLI `data_root` plus inventory `row.path` → joined-path `resolve` | Reject absolute/`..`, then canonical containment and file validation; returned path reused. Trace taints root, but inventory was also audited. | No static inventory escape found. Adversarial parent, absolute, sibling-prefix and symlink regressions reject; in-root aliases pass. Propose inapplicable under the stable private-tree contract, not under a hostile mutable-filesystem contract. |
| [96](https://github.com/siamakenna/perturb-LM/security/code-scanning/96) C:100 | Same root/join → `is_file` | `not path.is_relative_to(root) or not path.is_file()` short-circuits: an escaping canonical path never reaches `is_file`. | Containment is structural, not a string-prefix check. Same proposed disposition and mutable-filesystem limitation as 95. |
| [97](https://github.com/siamakenna/perturb-LM/security/code-scanning/97) C:112 | Operator `--data-root` → root `resolve` | Root selection precedes all inventory-relative operations. Directory aliases intentionally resolve. | Resolving the explicitly selected root is intended, not an inventory escape. Propose inapplicable for local caller; collaborator must confirm trusted-operator deployment scope. |
| [98](https://github.com/siamakenna/perturb-LM/security/code-scanning/98) C:113 | Canonical selected root → `is_dir` | Reject non-directory roots before reading inventory TIFFs. | Intended validation of the selected root; same proposed local-capability disposition as 97. |
| [99](https://github.com/siamakenna/perturb-LM/security/code-scanning/99) C:160 | Root + `row.path` → confined returned path → `stat` | All 95/96 checks precede this 32 MiB size check; actual content operations use the same returned path. | No static bypass found; same regression evidence and conditional proposed disposition as 95. Canonical-directory replacement races are not claimed solved. |
| [100](https://github.com/siamakenna/perturb-LM/security/code-scanning/100) C:241 | `npz-info`, `analyze`, or `compare` CLI NPZ filename → `stat` | Selected archive size bounded; archive member paths rejected; no extraction; object arrays rejected and loading uses `allow_pickle=False`. Three traces. | Intended archive read. Member names never select filesystem destinations. Propose inapplicable path traversal for local CLI, not blanket approval of arbitrary archives or callers. |
| [101](https://github.com/siamakenna/perturb-LM/security/code-scanning/101) C:429 | `analyze --out` → fixed neighbors TSV → exclusive `open` | Exclusive leaf creation, but old parent alias could redirect writes. | Genuine shared redirect defect; fixed by pinned output. Adjacent NPZ overwrite also reproduced and changed to `open('xb')`. Review remaining operator-selected destination flow. |
| [102](https://github.com/siamakenna/perturb-LM/security/code-scanning/102) C:557 | `scores-summary --scores` → text `open` | Explicit file selection; header, row, metric, coverage validation. Table fields never supply another pathname. | Intended selected-file read; no nested path authority. Propose inapplicable path traversal subject to local-caller review. |
| [103](https://github.com/siamakenna/perturb-LM/security/code-scanning/103) L:43 | Interactive terminal input → `Path(raw).expanduser()` | TTY required; empty/relative inputs rejected; file/directory existence checked; no shell execution of input. | Expansion is intentional, but audit found dangling pilot-output/working links accepted later. Fix freshness before resolving output leaf and at shell delegation. Review remaining intentional prompt path expansion separately. |

## Regression evidence and remaining decisions

The first run of `tests/test_phase4_path_security.py` against the original
implementation produced **5 failed, 10 passed**: all four output-alias cases
and the intervening NPZ-file case failed. The analyze alias case demonstrably
overwrote a sentinel in another directory. Other cases wrote output in the
wrong directory. These are behavioral reproductions, not analyzer cosmetics.

Tests cover containment for both image and metadata inventories; absolute and
parent-traversing names; sibling-prefix and symlink escapes; legitimate in-root
aliases and spaces; exclusive archive writes; dangling output/working links;
request and preparation alias retargeting; external manifests; and preservation
of the selected venv executable. No real inputs, approvals, inference, or Slurm
submission are exercised. The native worker and evaluator remain unchanged.

The previous validation is preserved: five files **91 passed, 30 subtests
passed**; Linux 3.11/3.12 **476 passed each** plus smoke workflows; package matrix
passed; broader local run **464 passed, 3 Torch-related collection errors,
30 subtests passed**, exit 1. These overlapping historical counts do not describe
the new revision and must not be added. Current test/check results are recorded
in PR #71 against the pushed security-fix SHA.

Collaborator decisions after reviewing the patch and fresh scan:

- Confirm the supported trust model: operator-selected top-level paths, reviewed
  private requests, stable private canonical directories, no untrusted service
  callers or privileged broker. If broader deployment is required, specify the
  capability boundary before extending the I/O implementation.
- Review each remaining alert using the table and full traces, especially the
  distinction between fixed output defects and deliberate selected-file reads.
  This review proposes dispositions; it does not dismiss alerts or authorize a
  gate bypass. Keep the PR draft while the security gate/review is outstanding.

The pilot bound, M0 conditions, evaluator, SciBERT workstream, unresolved model
assets/input approvals, and BUILT_NOT_RELEASED status are unchanged.

## Complete dataflow appendix at starting revision

### Alert 89

Flow 1, thread 1, every location in scanner order:

```text
scripts/comparator_tools.py:700:9-28 | parser.parse_args()
scripts/comparator_tools.py:700:5-6 | a
scripts/comparator_tools.py:703:37-48 | a.selection
scripts/comparator_tools.py:107:20-29 | selection
scripts/comparator_tools.py:116:44-53 | selection
scripts/comparator_tools.py:29:12-16 | path
scripts/comparator_tools.py:31:10-14 | path
```

Flow 2, thread 1, every location in scanner order:

```text
scripts/comparator_tools.py:700:9-28 | parser.parse_args()
scripts/comparator_tools.py:700:5-6 | a
scripts/comparator_tools.py:703:63-73 | a.settings
scripts/comparator_tools.py:107:49-57 | settings
scripts/comparator_tools.py:116:63-71 | settings
scripts/comparator_tools.py:29:12-16 | path
scripts/comparator_tools.py:31:10-14 | path
```

Flow 3, thread 1, every location in scanner order:

```text
scripts/comparator_tools.py:700:9-28 | parser.parse_args()
scripts/comparator_tools.py:700:5-6 | a
scripts/comparator_tools.py:703:75-80 | a.out
scripts/comparator_tools.py:107:65-68 | out
scripts/comparator_tools.py:226:42-70 | out / "image-inventory.json"
scripts/comparator_tools.py:29:12-16 | path
scripts/comparator_tools.py:31:10-14 | path
```

Flow 4, thread 1, every location in scanner order:

```text
scripts/prepare_native_launch.py:313:9-23 | p.parse_args()
scripts/prepare_native_launch.py:313:5-6 | a
scripts/prepare_native_launch.py:318:38-47 | a.request
scripts/prepare_native_launch.py:175:13-20 | request
scripts/prepare_native_launch.py:195:49-56 | request
scripts/prepare_native_launch.py:62:5-12 | request
scripts/prepare_native_launch.py:144:36-43 | request
scripts/comparator_tools.py:29:12-16 | path
scripts/comparator_tools.py:31:10-14 | path
```

### Alert 90

Flow 1, thread 1, every location in scanner order:

```text
scripts/comparator_tools.py:700:9-28 | parser.parse_args()
scripts/comparator_tools.py:700:5-6 | a
scripts/comparator_tools.py:703:37-48 | a.selection
scripts/comparator_tools.py:107:20-29 | selection
scripts/comparator_tools.py:115:29-38 | selection
scripts/comparator_tools.py:37:15-19 | path
scripts/comparator_tools.py:38:8-12 | path
```

Flow 2, thread 1, every location in scanner order:

```text
scripts/comparator_tools.py:700:9-28 | parser.parse_args()
scripts/comparator_tools.py:700:5-6 | a
scripts/comparator_tools.py:703:63-73 | a.settings
scripts/comparator_tools.py:107:49-57 | settings
scripts/comparator_tools.py:115:51-59 | settings
scripts/comparator_tools.py:37:15-19 | path
scripts/comparator_tools.py:38:8-12 | path
```

Flow 3, thread 1, every location in scanner order:

```text
scripts/prepare_native_launch.py:313:9-23 | p.parse_args()
scripts/prepare_native_launch.py:313:5-6 | a
scripts/prepare_native_launch.py:318:38-47 | a.request
scripts/prepare_native_launch.py:175:13-20 | request
scripts/prepare_native_launch.py:195:49-56 | request
scripts/prepare_native_launch.py:62:5-12 | request
scripts/prepare_native_launch.py:64:21-28 | request
scripts/comparator_tools.py:37:15-19 | path
scripts/comparator_tools.py:38:8-12 | path
```

### Alert 91

Flow 1, thread 1, every location in scanner order:

```text
scripts/comparator_tools.py:700:9-28 | parser.parse_args()
scripts/comparator_tools.py:700:5-6 | a
scripts/comparator_tools.py:703:37-48 | a.selection
scripts/comparator_tools.py:107:20-29 | selection
scripts/comparator_tools.py:115:29-38 | selection
scripts/comparator_tools.py:37:15-19 | path
scripts/comparator_tools.py:40:23-27 | path
```

Flow 2, thread 1, every location in scanner order:

```text
scripts/comparator_tools.py:700:9-28 | parser.parse_args()
scripts/comparator_tools.py:700:5-6 | a
scripts/comparator_tools.py:703:63-73 | a.settings
scripts/comparator_tools.py:107:49-57 | settings
scripts/comparator_tools.py:115:51-59 | settings
scripts/comparator_tools.py:37:15-19 | path
scripts/comparator_tools.py:40:23-27 | path
```

Flow 3, thread 1, every location in scanner order:

```text
scripts/prepare_native_launch.py:313:9-23 | p.parse_args()
scripts/prepare_native_launch.py:313:5-6 | a
scripts/prepare_native_launch.py:318:38-47 | a.request
scripts/prepare_native_launch.py:175:13-20 | request
scripts/prepare_native_launch.py:195:49-56 | request
scripts/prepare_native_launch.py:62:5-12 | request
scripts/prepare_native_launch.py:64:21-28 | request
scripts/comparator_tools.py:37:15-19 | path
scripts/comparator_tools.py:40:23-27 | path
```

### Alert 92

Flow 1, thread 1, every location in scanner order:

```text
scripts/comparator_tools.py:700:9-28 | parser.parse_args()
scripts/comparator_tools.py:700:5-6 | a
scripts/comparator_tools.py:703:75-80 | a.out
scripts/comparator_tools.py:107:65-68 | out
scripts/comparator_tools.py:217:16-44 | out / "image-inventory.json"
scripts/comparator_tools.py:43:16-20 | path
scripts/comparator_tools.py:44:10-14 | path
```

Flow 2, thread 1, every location in scanner order:

```text
scripts/comparator_tools.py:700:9-28 | parser.parse_args()
scripts/comparator_tools.py:700:5-6 | a
scripts/comparator_tools.py:711:17-22 | a.out
scripts/comparator_tools.py:374:5-8 | out
scripts/comparator_tools.py:438:19-22 | out
scripts/comparator_tools.py:58:12-15 | out
scripts/comparator_tools.py:60:16-36 | out / "summary.json"
scripts/comparator_tools.py:43:16-20 | path
scripts/comparator_tools.py:44:10-14 | path
```

Flow 3, thread 1, every location in scanner order:

```text
scripts/comparator_tools.py:700:9-28 | parser.parse_args()
scripts/comparator_tools.py:700:5-6 | a
scripts/comparator_tools.py:718:75-80 | a.out
scripts/comparator_tools.py:457:66-69 | out
scripts/comparator_tools.py:539:19-22 | out
scripts/comparator_tools.py:58:12-15 | out
scripts/comparator_tools.py:63:9-39 | out / "analysis-complete.json"
scripts/comparator_tools.py:43:16-20 | path
scripts/comparator_tools.py:44:10-14 | path
```

Flow 4, thread 1, every location in scanner order:

```text
scripts/prepare_native_launch.py:313:9-23 | p.parse_args()
scripts/prepare_native_launch.py:313:5-6 | a
scripts/prepare_native_launch.py:316:26-31 | a.out
scripts/prepare_native_launch.py:31:18-22 | path
scripts/prepare_native_launch.py:57:16-20 | path
scripts/comparator_tools.py:43:16-20 | path
scripts/comparator_tools.py:44:10-14 | path
```

### Alert 93

Flow 1, thread 1, every location in scanner order:

```text
scripts/comparator_tools.py:700:9-28 | parser.parse_args()
scripts/comparator_tools.py:700:5-6 | a
scripts/comparator_tools.py:703:75-80 | a.out
scripts/comparator_tools.py:107:65-68 | out
scripts/comparator_tools.py:216:16-19 | out
scripts/comparator_tools.py:49:16-20 | path
scripts/comparator_tools.py:50:8-12 | path
```

Flow 2, thread 1, every location in scanner order:

```text
scripts/comparator_tools.py:700:9-28 | parser.parse_args()
scripts/comparator_tools.py:700:5-6 | a
scripts/comparator_tools.py:711:17-22 | a.out
scripts/comparator_tools.py:374:5-8 | out
scripts/comparator_tools.py:428:16-19 | out
scripts/comparator_tools.py:49:16-20 | path
scripts/comparator_tools.py:50:8-12 | path
```

Flow 3, thread 1, every location in scanner order:

```text
scripts/comparator_tools.py:700:9-28 | parser.parse_args()
scripts/comparator_tools.py:700:5-6 | a
scripts/comparator_tools.py:718:75-80 | a.out
scripts/comparator_tools.py:457:66-69 | out
scripts/comparator_tools.py:538:16-19 | out
scripts/comparator_tools.py:49:16-20 | path
scripts/comparator_tools.py:50:8-12 | path
```

Flow 4, thread 1, every location in scanner order:

```text
scripts/comparator_tools.py:700:9-28 | parser.parse_args()
scripts/comparator_tools.py:700:5-6 | a
scripts/comparator_tools.py:722:17-22 | a.out
scripts/comparator_tools.py:544:5-8 | out
scripts/comparator_tools.py:642:16-19 | out
scripts/comparator_tools.py:49:16-20 | path
scripts/comparator_tools.py:50:8-12 | path
```

### Alert 94

Flow 1, thread 1, every location in scanner order:

```text
scripts/comparator_tools.py:700:9-28 | parser.parse_args()
scripts/comparator_tools.py:700:5-6 | a
scripts/comparator_tools.py:703:75-80 | a.out
scripts/comparator_tools.py:107:65-68 | out
scripts/comparator_tools.py:216:16-19 | out
scripts/comparator_tools.py:49:16-20 | path
scripts/comparator_tools.py:54:5-9 | path
```

Flow 2, thread 1, every location in scanner order:

```text
scripts/comparator_tools.py:700:9-28 | parser.parse_args()
scripts/comparator_tools.py:700:5-6 | a
scripts/comparator_tools.py:711:17-22 | a.out
scripts/comparator_tools.py:374:5-8 | out
scripts/comparator_tools.py:428:16-19 | out
scripts/comparator_tools.py:49:16-20 | path
scripts/comparator_tools.py:54:5-9 | path
```

Flow 3, thread 1, every location in scanner order:

```text
scripts/comparator_tools.py:700:9-28 | parser.parse_args()
scripts/comparator_tools.py:700:5-6 | a
scripts/comparator_tools.py:718:75-80 | a.out
scripts/comparator_tools.py:457:66-69 | out
scripts/comparator_tools.py:538:16-19 | out
scripts/comparator_tools.py:49:16-20 | path
scripts/comparator_tools.py:54:5-9 | path
```

Flow 4, thread 1, every location in scanner order:

```text
scripts/comparator_tools.py:700:9-28 | parser.parse_args()
scripts/comparator_tools.py:700:5-6 | a
scripts/comparator_tools.py:722:17-22 | a.out
scripts/comparator_tools.py:544:5-8 | out
scripts/comparator_tools.py:642:16-19 | out
scripts/comparator_tools.py:49:16-20 | path
scripts/comparator_tools.py:54:5-9 | path
```

### Alert 95

Flow 1, thread 1, every location in scanner order:

```text
scripts/comparator_tools.py:700:9-28 | parser.parse_args()
scripts/comparator_tools.py:700:5-6 | a
scripts/comparator_tools.py:703:50-61 | a.data_root
scripts/comparator_tools.py:107:37-41 | root
scripts/comparator_tools.py:112:5-9 | root
scripts/comparator_tools.py:156:30-34 | root
scripts/comparator_tools.py:96:19-23 | root
scripts/comparator_tools.py:99:13-23 | root / rel
```

### Alert 96

Flow 1, thread 1, every location in scanner order:

```text
scripts/comparator_tools.py:700:9-28 | parser.parse_args()
scripts/comparator_tools.py:700:5-6 | a
scripts/comparator_tools.py:703:50-61 | a.data_root
scripts/comparator_tools.py:107:37-41 | root
scripts/comparator_tools.py:112:5-9 | root
scripts/comparator_tools.py:156:30-34 | root
scripts/comparator_tools.py:96:19-23 | root
scripts/comparator_tools.py:99:5-9 | path
scripts/comparator_tools.py:100:45-49 | path
```

### Alert 97

Flow 1, thread 1, every location in scanner order:

```text
scripts/comparator_tools.py:700:9-28 | parser.parse_args()
scripts/comparator_tools.py:700:5-6 | a
scripts/comparator_tools.py:703:50-61 | a.data_root
scripts/comparator_tools.py:107:37-41 | root
scripts/comparator_tools.py:112:12-16 | root
```

### Alert 98

Flow 1, thread 1, every location in scanner order:

```text
scripts/comparator_tools.py:700:9-28 | parser.parse_args()
scripts/comparator_tools.py:700:5-6 | a
scripts/comparator_tools.py:703:50-61 | a.data_root
scripts/comparator_tools.py:107:37-41 | root
scripts/comparator_tools.py:112:5-9 | root
scripts/comparator_tools.py:113:12-16 | root
```

### Alert 99

Flow 1, thread 1, every location in scanner order:

```text
scripts/comparator_tools.py:700:9-28 | parser.parse_args()
scripts/comparator_tools.py:700:5-6 | a
scripts/comparator_tools.py:703:50-61 | a.data_root
scripts/comparator_tools.py:107:37-41 | root
scripts/comparator_tools.py:112:5-9 | root
scripts/comparator_tools.py:156:30-34 | root
scripts/comparator_tools.py:96:19-23 | root
scripts/comparator_tools.py:99:5-9 | path
scripts/comparator_tools.py:104:12-16 | path
scripts/comparator_tools.py:156:16-48 | confined_file(root, row["path"])
scripts/comparator_tools.py:156:9-13 | path
scripts/comparator_tools.py:160:12-16 | path
```

### Alert 100

Flow 1, thread 1, every location in scanner order:

```text
scripts/comparator_tools.py:700:9-28 | parser.parse_args()
scripts/comparator_tools.py:700:5-6 | a
scripts/comparator_tools.py:705:45-50 | a.npz
scripts/comparator_tools.py:237:17-21 | path
scripts/comparator_tools.py:241:8-12 | path
```

Flow 2, thread 1, every location in scanner order:

```text
scripts/comparator_tools.py:700:9-28 | parser.parse_args()
scripts/comparator_tools.py:700:5-6 | a
scripts/comparator_tools.py:708:17-22 | a.npz
scripts/comparator_tools.py:371:5-9 | path
scripts/comparator_tools.py:382:49-53 | path
scripts/comparator_tools.py:237:17-21 | path
scripts/comparator_tools.py:241:8-12 | path
```

Flow 3, thread 1, every location in scanner order:

```text
scripts/comparator_tools.py:700:9-28 | parser.parse_args()
scripts/comparator_tools.py:700:5-6 | a
scripts/comparator_tools.py:718:30-46 | a.representation
scripts/comparator_tools.py:457:5-20 | representations
scripts/comparator_tools.py:466:15-23 | filename
scripts/comparator_tools.py:467:9-13 | path
scripts/comparator_tools.py:468:47-51 | path
scripts/comparator_tools.py:237:17-21 | path
scripts/comparator_tools.py:241:8-12 | path
```

### Alert 101

Flow 1, thread 1, every location in scanner order:

```text
scripts/comparator_tools.py:700:9-28 | parser.parse_args()
scripts/comparator_tools.py:700:5-6 | a
scripts/comparator_tools.py:711:17-22 | a.out
scripts/comparator_tools.py:374:5-8 | out
scripts/comparator_tools.py:429:11-40 | out / "neighbors.private.tsv"
```

### Alert 102

Flow 1, thread 1, every location in scanner order:

```text
scripts/comparator_tools.py:700:9-28 | parser.parse_args()
scripts/comparator_tools.py:700:5-6 | a
scripts/comparator_tools.py:721:17-25 | a.scores
scripts/comparator_tools.py:543:5-9 | path
scripts/comparator_tools.py:557:10-14 | path
```

### Alert 103

Flow 1, thread 1, every location in scanner order:

```text
scripts/prepare_native_launch.py:40:15-32 | input(f"{key}: ")
scripts/prepare_native_launch.py:40:9-12 | raw
scripts/prepare_native_launch.py:43:13-22 | Path(raw)
```
