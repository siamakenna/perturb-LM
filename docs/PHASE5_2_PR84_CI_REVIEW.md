# PR #84 source and CI review (#30, #52)

Prepared October 22, 2026 against PR head
`0ff10b3f7c1f319ece0864c57111f349eab4307d`.

## Evidence inspected

The source-only review ZIP has SHA-256
`a80a030657955a4dfeee3eda90a675c3c02d2ca9204d93a21e019de6aeced263`.
Its internal file hashes pass. It contains the public source, PR/check metadata,
alert #150 instances and Python SARIF, and an excerpt of package artifact
12436732415. Original private profiles and mappings were not supplied or read.

## Supplemental JSON input hardening

Alert #150 (`py/path-injection`) identifies four flows into the generic
`cohort.checksum` file read: validation and repository-context JSON in the census
CLI, and census-receipt and reference-manifest JSON in the readiness CLI.
Those inputs were parsed and hashed in separate reads.

The two CLIs now obtain each JSON value and SHA-256 from one bounded snapshot.
The new helper confines access beneath an explicitly selected directory,
rejects parent traversal and symlinks below that directory, uses descriptor-relative
reads, checks file identity around reads, enforces a 4 MiB limit, and rejects
duplicate keys, non-finite numbers and non-object documents. Trusted-root aliases
above the nominated directory remain supported, including macOS path aliases.
The root directory and its ancestors remain trusted inputs.

`--evidence-root`, `--census-root` and `--reference-root` default to the invocation
directory. Updated runbook examples explain how to nominate external input
directories. Both CLIs include the new helper in future implementation hashes.

This change addresses the four supplied supplemental JSON flows. It does not
make every existing CSV/TSV or private-input read atomic. The shared cohort
checksum helper, cohort definitions, guide identities, F10 guard and historical
evidence files are unchanged. CodeQL must analyze the pushed revision before
the remote gate can be described as resolved.

## Python 3.10 package failure

The supplied artifact contains only `summary.json`: `wheel-base` failed with
`CalledProcessError` and no test counts. The workflow uploads that summary,
not the underlying private log. Therefore the original installation failure's
cause cannot be established from this artifact. No dependency pin was changed
without evidence.

The validator now records its Python version and a static `failure_step` in the
public summary and terminal failure message. The phases distinguish environment
creation, dependency installation/checks, installed-origin/isolation checks,
environment capture, and acceptance-test execution/verification. Command
arguments, paths, raw logs and exception messages remain outside the summary.
Failure status and exit behavior remain unchanged.

The artifact records source commit `022002d5f259d9e34a80aa4544c413923da8597b`,
while its Actions run records the PR head above. A pull-request merge checkout
could explain this difference; that explanation was not independently verified.

The diagnostic improvement is not a demonstrated repair of the Python 3.10
installation failure. Re-run the package check after publication and inspect
the actual new summary.

## Validation actually executed

Linux x86-64, CPython 3.12.14:

- 35 unittest methods passed, with 57 successful subtests and no skips, across
  JSON boundary/CLI integration, artifact failure diagnostics and the existing
  Phase 5.1 rotation tests.
- The public-copy consistency check passed.
- Changed Python files parse using Python 3.10's syntax grammar.

Python 3.10 runtime, macOS execution, the full pytest suite, Ruff, CodeQL and the
wheel/sdist installation matrix were not run in this review environment.
Downloads of the needed Python/runtime packages were blocked by HTTP 403.
Syntax compatibility is not runtime validation.

## Publication and scientific boundary

This patch was prepared offline. Use the accompanying Mac helper to apply the
reviewed file changes in a fresh checkout, run available synthetic checks,
commit and push to PR #84, and verify its remote SHA. Keep the PR unmerged and
record new-head CI outcomes separately.

No historical census, HGNC preparation or Batch8/MOA analysis was repeated.
No research files were transferred, scientific approval granted, model run or
Biowulf resource used. The cross-guide experiment remains proposed and unapproved.
