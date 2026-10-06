# Post-merge package validation: 679f9b37c5c7

## Recorded execution

This record summarizes the operator's completed Biowulf validation output
from October 6, 2026. It does not represent a newly executed test run.

- Tested source: `679f9b37c5c7f2da2474b7a90a947dbda6f3626f`
- Distribution: `perturb-lm`
- Version: `0.2.0a1`
- Platform: Linux
- Python: `3.11.11`
- Slurm job: `32068960`
- Final scheduler state: `COMPLETED`
- Final scheduler exit code: `0:0`
- Final wrapper exit code: `0`
- Aggregate artifact-validation result: `PASS`
- Source checkout unchanged: `true`

## Independent installation checks

| Installation | Passed | Failed | Errors | Skipped |
|---|---:|---:|---:|---:|
| Wheel / base | 14 | 0 | 0 | 0 |
| Wheel / pixel | 15 | 0 | 0 | 0 |
| Source distribution / base | 14 | 0 | 0 | 0 |
| Source distribution / pixel | 15 | 0 | 0 | 0 |

The stage counts overlap and must not be summed as distinct tests.

The repository's build and artifact-validation tools were used:

- `scripts/build_release_candidate.py`
- `scripts/validate_release_artifacts.py`

The artifact validator installs each distribution in independent environments
and exercises its covered public API and image examples outside the checkout.

## Exact artifact hashes

Wheel: `perturb_lm-0.2.0a1-py3-none-any.whl`

SHA-256:
`031f1be0aa60be66f278bee95e15816b63b664a83f2a5aa961ff1650e3298b48`

Source distribution: `perturb_lm-0.2.0a1.tar.gz`

SHA-256:
`abb8b02bd1a6b400f25931c84270f646081a90c2426bf8102d3b2d2e5a3024fe`

Both files passed checksum verification. These hashes identify this build
only and must not be assigned to another revision or rebuild.

Original machine-readable records were retained in the execution workspace:

- `dist/candidate/provenance.json`
- `outputs/package-validation/summary.json`

## Scope and limitations

This is artifact-installation evidence for the recorded Linux/Python environment.
It is not a new full-source-suite result, pretrained-model benchmark,
biological validation, or confirmation of all supported platform combinations.

The build provenance recorded `BUILT_NOT_RELEASED`. This note does not
authorize distribution or establish that a release has been published.

The build emitted a warning that no `LICENSE*` files matched.
Any public distribution must follow the project's release checklist and
recorded ownership/license decision, including issue #32 where applicable.

This documentation commit does not change the source SHA that was tested.
Raw logs, environments, biomedical inputs, embeddings, and model weights
are not included.
