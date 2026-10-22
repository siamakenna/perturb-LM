# Phase 5.2 next-device handoff

**Engineering checkpoint; scientific execution remains unapproved.**

- Repository: https://github.com/siamakenna/perturb-LM
- Working branch: `science/phase5-2-cross-guide-readiness-20261022T144928Z`.
- Pull request: https://github.com/siamakenna/perturb-LM/pull/84
- Reviewed source revision before this handoff commit: `e470bec0bd8a934bc5de2a7ba3766c20e0797779`.
- Evidence captured at: `2026-10-22T17:54:35.265053+00:00` (UTC).
- Local review ZIP SHA-256: `1ec5a08ae1db3ddb3c94c420f028e236bd72264ddd109584a766f5fe7851dc75`.

This document records a source checkpoint. The commit adding this document
has a different SHA. Assess its checks separately; the statuses below do
not establish that later commits passed CI. No merge or alert dismissal
is authorized by this handoff.

## Engineering evidence

Capture completeness: **PARTIAL**.
Exact-source Python CodeQL analysis: **unavailable; do not infer zero alerts**.

| Captured check | State | Conclusion |
| --- | --- | --- |
| Artifact installs (Python 3.10, minimum) | completed | failure |
| Artifact installs (Python 3.11, current) | in_progress | unavailable |
| Artifact installs (Python 3.12, current) | completed | success |
| Constrained install and synthetic smoke (3.11) | completed | success |
| Constrained install and synthetic smoke (3.12) | completed | success |
| Manual remote JUMP profile smoke | completed | skipped |
| Synthetic tests and smoke workflows (3.11) | completed | success |
| Synthetic tests and smoke workflows (3.12) | completed | success |
| changes | completed | success |
| web | completed | success |

### Package evidence

Wheel/base artifact status: `REVIEW_REQUIRED`.
Artifact build revision: `3dfb4b7f95c925ab06e95c82bd8fb3aa47d06e76`.
Installer categories: `dependency_resolution_conflict`.
Reported installer requirement: `numpy==2.2.6`.

Captured minimum-dependency policies:

- artifact-build at `3dfb4b7f95c925ab06e95c82bd8fb3aa47d06e76`: `numpy==2.2.6`, `pandas==2.2.3`, `scipy==1.12.0`, `scikit-learn==1.4.2`, `scikit-image==0.22.0`.
- captured-pr-head at `e470bec0bd8a934bc5de2a7ba3766c20e0797779`: `numpy==1.26.4`, `pandas==2.2.3`, `scipy==1.12.0`, `scikit-learn==1.4.2`, `scikit-image==0.22.0`.
- captured-main at `ef7e74ac2f76b6c111d0f8bac2a9f2ff0e7ef6f7`: `numpy==2.2.6`, `pandas==2.2.3`, `scipy==1.12.0`, `scikit-learn==1.4.2`, `scikit-image==0.22.0`.

These are diagnostic observations. A NumPy policy discrepancy was found
during review. Establish the executed build's compatible dependency set
before changing pins; inspect exact-source CodeQL traces before changing
path handling. Missing evidence and failed checks remain blockers.

## Scientific and data boundary

The research priority is biological interpretation and confounding control,
with exact-reagent recovery kept separate from same-gene/different-guide
agreement. DINOv2 remains optional. No completed census, nomenclature
preparation, Batch8 or MOA result should be rerun merely to recreate it.

Earlier source-Mac handoff reports verified 12 profile hashes and 11 source
metadata hashes. This document does not verify their presence or bytes on
another device. Private profiles, mappings and local logs are not included
in this GitHub update. Keep upstream preprocessing, culture independence,
guide biology and the unchanged F10 guard explicit in subsequent review.

No model inference, training, new scientific scoring, bulk data transfer or
Biowulf use is authorized. Biological and preprocessing review must precede
selection and approval of a scored experiment.

## Continue on another device

Use an authenticated GitHub CLI and a fresh checkout:

```bash
CHECKOUT="$(mktemp -d "$HOME/Downloads/perturb-lm-next.XXXXXX")"
gh repo clone siamakenna/perturb-LM "$CHECKOUT" -- --single-branch \
  --branch science/phase5-2-cross-guide-readiness-20261022T144928Z
cd "$CHECKOUT"
git status --short
git rev-parse HEAD
git ls-remote origin refs/heads/science/phase5-2-cross-guide-readiness-20261022T144928Z
cat docs/PHASE5_2_NEXT_DEVICE_HANDOFF.md
gh pr view 84 --repo siamakenna/perturb-LM --json url,state,headRefOid,isDraft
gh pr checks 84 --repo siamakenna/perturb-LM
```

Read AGENTS.md, docs/PHASE5_2_CONTINUATION.md and
docs/PHASE5_2_PR84_CI_REVIEW.md. Resolve current-head engineering failures
from their actual evidence, preserve existing work, and keep PR84 unmerged.
Private scientific work requires original-byte provenance and separate
execution approval. No collaborator message has been sent.
