# PR #84 source and CI follow-up (#30, #52)

October 22, 2026. Package repair prepared against the supplied source checkpoint
`e470bec0bd8a934bc5de2a7ba3766c20e0797779`. A subsequent source-Mac publication
receipt verified the handoff-only commit
`9814a061d8af2507c0f7c02bf8eb2df5bfe9304e`. This review environment did not
independently authenticate to GitHub.

## Confirmed package failure

The new review ZIP has SHA-256
`1ec5a08ae1db3ddb3c94c420f028e236bd72264ddd109584a766f5fe7851dc75`.
Its internal checksums pass. Public policy-file receipts include Git blob and
SHA-256 bindings. Artifact 12444304259 from run 39822753612 records Python
3.10.22 and a dependency-resolution conflict at `install_dependencies`.

The artifact was built from GitHub's merge revision
`3dfb4b7f95c925ab06e95c82bd8fb3aa47d06e76`, whose verified parent list is:

1. main: `ef7e74ac2f76b6c111d0f8bac2a9f2ff0e7ef6f7`;
2. PR source: `e470bec0bd8a934bc5de2a7ba3766c20e0797779`.

The actual build and captured main both selected NumPy 2.2.6 while retaining
SciPy 1.12.0. SciPy 1.12.0 requires NumPy `>=1.22.4,<1.29.0`, so those pins
cannot be resolved together. The PR-head file still showed NumPy 1.26.4;
looking only at that file concealed the integration failure. The two earlier
public summaries lacked pip's error text; the bounded diagnostic and immutable
merge-policy receipts now establish this specific conflict.

| Dependency | Supplied PR head | Executed merge/main | Repaired CI cohort |
| --- | --- | --- | --- |
| NumPy | 1.26.4 | 2.2.6 | 2.2.6 |
| pandas | 2.2.3 | 2.2.3 | 2.2.3 |
| SciPy | 1.12.0 | 1.12.0 | 1.15.3 |
| scikit-learn | 1.4.2 | 1.4.2 | 1.4.2 |
| scikit-image | 0.22.0 | 0.22.0 | 0.25.2 |

The repair preserves main's NumPy update and the documented sklearn 1.4.2
boundary. It advances SciPy and scikit-image to maintenance releases whose
published requirements accommodate NumPy 2.2.6 and Python 3.10. Scikit-image
0.25.2 builds with NumPy 2; this also avoids relying on the older 0.22 build
cohort under the new NumPy selection. Scikit-learn 1.4.2 explicitly supports
NumPy 2; the former assumption that it required NumPy 1.x was incorrect.

The existing matrix label `minimum` identifies this lower-sklearn cohort. It
does not claim to exercise every declared dependency floor or every Cartesian
combination of permitted versions. Package-declared dependency ranges, matrix
check names, acceptance/isolation checks and normal merge-checkout CI remain
unchanged. Main's unrelated setup-python and optional Torch changes are left
to the existing merge integration; this repair does not overwrite them.
The reason main originally changed NumPy was not established, and no claim of
vulnerability-free dependencies is made.

The source checks supporting version selection are:

- [SciPy 1.12.0 requirements](https://raw.githubusercontent.com/scipy/scipy/v1.12.0/pyproject.toml): NumPy below 1.29.
- [SciPy 1.15.3 requirements](https://raw.githubusercontent.com/scipy/scipy/v1.15.3/pyproject.toml): Python >=3.10 and NumPy >=1.23.5,<2.5.
- [scikit-image 0.25.2 requirements](https://raw.githubusercontent.com/scikit-image/scikit-image/v0.25.2/pyproject.toml): Python >=3.10, NumPy >=1.24, SciPy >=1.11.4; builds use NumPy >=2.
- [sklearn 1.4.2 release notes](https://scikit-learn.org/1.4/whats_new/v1.4.html): NumPy 2 support.
- PyPI release files for [SciPy 1.15.3](https://pypi.org/project/scipy/1.15.3/#files) and [scikit-image 0.25.2](https://pypi.org/project/scikit-image/0.25.2/#files) include CPython 3.10 Linux x86-64 wheels.

Compatible published ranges and available wheels are not a substitute for an
actual install/import or artifact acceptance run. Python 3.10's installed-wheel
and sdist/base/pixel matrix must pass on the new commit before this package gate
can be called resolved.

## CodeQL remains a separate gate

The latest archive has no Python CodeQL analysis matching e470bec. Its exported
alerts #150, #153 and #154 still refer to the earlier 8f78d9b source revision.
The collector timed out with partial evidence and queried only the head ref.
GitHub's [code-scanning API](https://docs.github.com/en/rest/code-scanning/code-scanning)
documents PR analyses on `refs/pull/84/merge` and supports a PR-number filter.
The head-only query could therefore miss an integration analysis. The corrected
collector searches PR analyses and binds an accepted merge SHA to its actual
parents, including the captured PR head. No current security verdict or failure
to run CodeQL can be inferred from the earlier absence alone. No alerts were
dismissed or suppressed, and no security settings were changed.

The previous path fix remains unchanged: the invocation directory is the
independent confinement anchor, root flags can only narrow it, reads begin at
the literal current-directory descriptor and descendants use no-follow flags.
JSON is bounded to 4 MiB and each HGNC TSV to 32 MiB. Parsing and verification
use the same bytes, and aliases above the invocation directory remain supported.
Existing private mapping/provenance readers and the shared checksum helper are
not claimed universally atomic. Review the actual new-head analysis and gate
before making another security change or declaring the gate clear.

## Validation and publication limits

This repair changes only the fixed CI cohort and this engineering record.
A local synthetic Git merge using the captured PR/main policy files confirmed
that the forward NumPy change coalesces, the repaired cohort survives, and main's
pyproject/workflow bytes are preserved. This is merge-behavior evidence, not
runtime package validation. The accompanying kit records the checks actually
executed in the review environment separately from checks performed later on
the Mac or GitHub. Python 3.10, the repaired dependency environment, CodeQL and
the complete artifact matrix were not executed in the review environment.

The Mac helper uses a fresh checkout and environment, installs the selected
software dependencies, checks exact versions and imports, and runs existing
synthetic package/pixel acceptance tests before a non-force push. Local editable
installation is a separate step from binary-only dependency installation.
Its Python version is recorded; a Python 3.12 Mac pass is not a Python 3.10 pass.
Publication SHA verification and current-head CI remain separate observations.

No private datasets or logs are committed. No historical census, nomenclature,
Batch8 or MOA calculation was repeated. No pretrained inference, training,
scientific scoring, collaborator contact, release, deployment, PR merge or
Biowulf use occurred. The cross-guide scientific experiment remains proposed
and unapproved. Keep the existing next-device handoff as a historical checkpoint;
this record supplies the subsequent, source-bound package diagnosis.
