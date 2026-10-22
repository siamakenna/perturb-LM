# PR #84 source and CI follow-up (#30, #52)

Prepared October 22, 2026 against supplied PR head
`8f78d9b984dc61bfe852bbb609791d8351de35ea`.

## Verified checkpoint and evidence

The follow-up review ZIP has SHA-256
`38b8138157ea7354b50feee6c2b54bdaeb6769bbd9c2b9cc0334b4a315733f09`.
Its internal checksums pass. The source archive matches all nine reviewed
post-patch file hashes from the previous kit. The source-machine verification
report records the local commit, remote branch and PR head at the SHA above.
This confirms the previous push succeeded; the earlier helper stopped at its
post-push comparison. The transient mismatch's cause was not established.

The captured checks have eleven successes, one skipped manual workflow, and
two failures: CodeQL and Python 3.10 minimum-dependency artifact installation.
Python 3.11 and 3.12 artifact matrices passed at this checkpoint. These are
uploaded GitHub observations, not a live authenticated query from this review.
No original private profiles or mappings were supplied or read.

## Path-flow review and follow-up

The first patch bound four supplemental JSON parses and hashes to bounded
snapshots. Current SARIF shows that alert #150 still reaches the shared
`cohort.checksum` through the HGNC approved and withdrawn TSV paths.
Alerts #153 and #154 concern stat/open of the freely selected JSON root itself.
The first patch therefore did not resolve the security gate.

The follow-up makes the invocation directory the independent confinement
anchor. `--evidence-root`, `--census-root` and `--reference-root` default to it
and can only select subdirectories beneath it. Root arguments no longer widen
the boundary. Opening begins at the literal current directory, then walks
root/input components using directory descriptors and no-follow flags.
Canonical boundary checks, file identity checks and nonregular-file rejection
remain. Aliases above the invocation directory remain supported on macOS;
symlinks beneath it do not.

Both HGNC TSVs now use the same bounded snapshot reader as the supplemental
JSONs. Their parsed rows and verified reference hashes come from the same
bytes. JSON retains its 4 MiB limit. HGNC TSVs have a separate 32 MiB bound:
the preserved approved reference is 16,982,321 bytes and cannot use the JSON
limit. The updated examples explain how to choose a common input anchor,
use narrower roots and keep fresh outputs beneath the ignored repository
output directory. This is an input-access policy change, not a new science run.

The shared cohort checksum helper and existing private mapping/provenance
handling remain unchanged. This patch does not certify all existing readers
as atomic, authenticate the operator's chosen working directory, or change
cohort definitions, gene/guide rules, F10 handling or historical evidence.
CodeQL must analyze the pushed follow-up before its gate can be called resolved.
No alerts were dismissed, relabelled or suppressed.

## Python 3.10 installation evidence

Artifact 12442928590 from run 39819113634 matches this PR head. Its summary
records validator Python 3.10.22, `wheel-base`, `CalledProcessError`, and
`failure_step: install_dependencies`. It contains no pip diagnostic text.
The workflow did not upload its raw private log, so this packet cannot identify
a particular package, resolver conflict, index failure or compiler failure.
No dependency pin or accepted Python version was changed speculatively.

The follow-up adds bounded, allowlisted pip failure diagnostics to the public
summary. Raw logs, arbitrary command arguments, paths, URLs and exception
messages remain local. The failure step, failing exit status and all artifact
acceptance/isolation checks remain enforced. This improves the next failing
run's evidence; it is not a demonstrated repair of the dependency failure.

The artifact's build source commit is
`8712d616989629545b73837638a594b34843e53d`, while its Actions run records the
PR head above. A pull-request merge checkout could explain this difference;
that explanation has not been independently verified. Preserve both fields.

## Validation and limits

Validation of this follow-up uses synthetic inputs only. On Linux x86-64,
CPython 3.12.14, 46 unittest methods and 61 subtests passed with no skips.
The public-copy check and Python 3.10 syntax parsing passed. Nine separate
offline publication-helper tests also passed. The packaged validation receipt
records these checks separately and lists runtime limits.
Python 3.10 runtime, macOS execution, the full pytest suite, Ruff, CodeQL and
the wheel/sdist installation matrix cannot be claimed from the Linux review
environment. Earlier dependency/runtime downloads returned HTTP 403.
Python 3.10 syntax parsing is not Python 3.10 runtime validation.

The prior patch passed 35 unittest methods and 57 subtests here. The user's
Mac subsequently reported those focused suites, the public-copy check and
existing Phase 5 pytest suites passing before the verified push. Those
historical checks are not substituted for follow-up validation.

## Publication and scientific boundary

The Mac helper applies only reviewed files in a fresh checkout, runs synthetic
checks, commits and pushes to PR #84, then verifies local, branch and PR SHAs.
It retries read-only publication observations and records all compared SHAs;
it never retries a push or uses force. Keep the PR unmerged and record the
new head's checks separately. A successful source push does not imply green CI.

No historical census, HGNC preparation or Batch8/MOA analysis was repeated.
No research files were transferred, scientific approval granted, model run,
collaborator contacted or Biowulf resource used. The cross-guide experiment
remains proposed and unapproved.
