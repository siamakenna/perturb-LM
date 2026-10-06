# Phase 4 alpha release candidate

Candidate version: **0.2.0a1**. This document is a preparation record, not a
publication announcement. Distribution: `perturb-lm`; imports: `perturb_lm`;
estimator API: `perturb_lm.sklearn_api`. The single version source is
`src/perturb_lm/_version.py`, consumed by distribution metadata and imports.

## Integration and existing acceptance

Inspected origin/main: `ab0312b693785598cfbcff74dce081e1752e3899`.
PR #58 is the original pixel baseline, with CI dependency fix
`7734175ff63bf70bda57480e689aeb7617d4452d`. PR #59 contains that baseline
plus the installed image workflow and includes the pixel extra in CI.
Both remain subject to human integration; neither was merged for this work.

Acceptance branch `test/phase4-linux-acceptance` at
`41c2ed614ed014211a5f8042e28d692d5be3d03f` adds only the runner, runner
tests, Slurm wrapper, documentation and summary to application revision
`3549dd5e66381be33ebaf84d10590edfdc191918`.
The summary's runner SHA-256
`9114af46e8b27919212c52ce8bd02f6b78514620ffb852c2ab8b25659056d70f`
matches the committed runner bytes.

Recorded Linux Python 3.11.11 evidence: images 43/43, comparators 3/3,
repository 298/298, zero failures/errors/skips, all exits 0,
`source_unchanged=true`, overall PASS. Counts overlap; do not sum them.
The image stage includes the installed-wheel CLI test. The application SHA
legitimately precedes the evidence commit; no provenance was rewritten.
GitHub's full-dependency Python 3.11 and 3.12 runs also each reported 298 passed
at that application revision. Cancelled CodeQL jobs reported runner-allocation
failure; those are not code test failures.

This evidence validates the existing application, not this newer candidate.
Bundled resource loading, version metadata and estimator validation changed
here, so new package/source CI must pass. An identical Biowulf run of the old
revision adds no evidence. New Linux validation can run in GitHub CI; there is
no need for protected datasets, credentials or a new Biowulf submission.

## Changes and limitations

- Wheel/sdist package policy resources without requiring a checkout.
- Fail clearly for reordered morphology columns/target indices and modified
  fitted parameters; preserve reference-only fitting and immutable inference.
- Document and execute numeric morphology, explicit retrieval scoring and
  image CLI examples against installed artifacts.
- Build/provenance and fresh environment acceptance for base and pixel extras.
- Support Python 3.10–3.12 and scikit-learn >=1.4,<2, with explicit minimum
  and current dependency jobs. Broader interpreter support is not claimed.

The CLI's analyze/fit/search and saved-state application are retained. The
version bump does not migrate saved pixel states; the extractor hash and exact
runtime dependency checks still apply. Base imports do not load Torch,
Transformers or optional image libraries. No model checkpoints are bundled.

The source-only benchmark dispatcher, Slurm planning scripts and historical
result verifier continue to need a checkout. Production gates, plan_only,
provisional M1/M5 restrictions and disabled backends are unchanged. Synthetic
tests do not validate biological relevance, segmentation accuracy against
independent annotations, batch generalization or pretrained-data independence.

## Reproducible candidate build and checks

Use a clean committed checkout on a supported Python version:

```bash
python -m pip install build twine
python scripts/build_release_candidate.py --out dist/candidate
python scripts/validate_release_artifacts.py \
  --dist dist/candidate --out outputs/package-validation
```

The first command builds sdist then wheel from that source distribution and
checks package metadata. `provenance.json` records the full source SHA,
unchanged-source assertion, version and each artifact's SHA-256.
`SHA256SUMS` is suitable for `sha256sum -c`.

The second command verifies checksums, creates four independent environments
(wheel/base, wheel/pixel, sdist/base, sdist/pixel), installs the exact artifact
without editable paths or cached package wheels, runs pip check, asserts the
import location, and executes public API tests/examples outside the checkout.
No parent-environment site-packages are reused. Dependency wheels can come
from the configured public package index; no model/dataset download occurs.
Private logs/XML remain under the ignored output directory. Only the aggregate
summary is suitable for reviewed sharing.

The `Package candidate` workflow repeats this on Linux/Python 3.10–3.12,
including the sklearn 1.4.2 boundary. Existing CI retains complete comparator
dependencies. Candidate workflows have read-only repository permissions and
upload aggregate summaries automatically; candidate archives require explicit
manual workflow dispatch with `upload_candidate=true`. They contain no
publication step. Bookkeeping-only synchronized PR updates retain prior
artifact evidence; application, packaging and unknown file changes rebuild.
Inspect workflow diffs and successful results before approval.

The reviewed Biowulf aggregate evidence in PR #61 covers exactly
`a6ce43c9db80bb41e8884a892dfe65cf480009e0`, not a later workflow-only commit.
Do not repeat its accepted build or rewrite its source/checksums. Final
integration and owner-approved licensing changes require identifying a new
release source and validating its exact artifacts before publication.

## Human publication checklist

1. Review/integrate pixel, acceptance and package PRs in dependency order.
   After merges, synchronize dependent branches with ordinary merge commits;
   preserve acceptance provenance. Do not retest identical accepted code.
2. Review current package/source CI and candidate artifact checksums; builds
   on PR merge commits identify that exact SHA. Rebuild from the approved
   release source revision before publication.
3. Resolve ownership/license issue #32 before distributing a public alpha.
   No license decision is inferred by this change.
4. With explicit publication approval, create the approved version tag and a
   GitHub **prerelease**, attaching the newly built wheel/sdist, checksums and
   provenance. The old 0.1.0 diagnostic wheel is not this artifact.
5. Configure TestPyPI/PyPI project ownership and trusted publishing separately,
   using an approved GitHub environment and restricted publisher workflow.
   Validate TestPyPI installation before authorizing PyPI publication. Never
   commit registry tokens or reuse a version already published to an index.

No tag, GitHub release, TestPyPI upload or PyPI upload is created by these tools.

## Collaboration log

- Verified live PR heads, main SHA, dependency relationship and Linux evidence.
- Verified runner bytes and preserved the original tested application SHA.
- Implemented package version/resource fixes, estimator contracts, artifact
  build/validation tools and a nonpublishing Linux package workflow.
- Kept comparator/statistical expansion out of the release-readiness changes.
