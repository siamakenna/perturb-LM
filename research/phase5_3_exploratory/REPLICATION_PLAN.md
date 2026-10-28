# Parallel development and independent replication

26 October 2026. Metadata-first plan, not completed new experiments.

The current executable work has three linked questions: morphology concordance,
query information and technical-layout sensitivity. They share four plates.
Keep one primary effect and the prespecified sensitivity in the report, including
unfavorable or unavailable results. Do not count these as independent studies.

## Next data selection

| Candidate | Useful question | Limitation to resolve first |
| --- | --- | --- |
| JUMP Target-1/Target-2 compounds | Does a relationship survive changed layouts? | Full chemical identity, conditions and preprocessing must agree. This is a compound comparison; the official resource documents one CRISPR layout version. |
| Unused JUMP-MOA acquisitions | Does the endpoint survive position and acquisition changes? | The source MOA annotations need scrutiny. Prior P3/P4 analyses are development data, not an untouched test set. |
| cpg0016 compound data from another site | Does a frozen design generalize to an unseen data-generating site? | Select a bounded common-identity, matched-condition cohort and document site/culture/preprocessing lineage before any profile download. |
| cpg0016 CRISPR | Does a related genetic endpoint transfer? | Production perturbations use pooled guides per gene. They do not automatically replicate an individual-guide comparison. |

The official JUMP-MOA resource describes 90 compounds in 47 annotated MOA classes,
with four positions per compound, and cautions about mechanism annotations.
The scope pilot cpg0002 varies imaging systems; such variation does not by itself
prove independent cultures. The production compound data are a stronger next
candidate for cross-site evaluation once exact identities and conditions are bound.

## Concrete next deliverable

Create a metadata-only holdout selection with source revision/hash, identity
join key, matched treatment/acquisition conditions, independent-unit evidence,
preprocessing fit scope, candidate coverage and an explicit development/test
boundary. Choose it before inspecting new profile scores. Download only the
selected bounded cohort after that selection. No bulk acquisition is part of
this transfer kit.

For a paper, the combined argument should explain whether annotated biological
agreement survives information limits and acquisition shortcuts. A positive
within-cohort effect is feasibility evidence. An untouched acquisition/site
cohort is the next substantial step toward a generalization claim. No particular
journal tier or manuscript outcome is guaranteed by increasing run count.

## Primary public sources inspected

- [JUMP-Target](https://github.com/jump-cellpainting/JUMP-Target): compound layout
  versions and the single CRISPR layout version.
- [JUMP-MOA](https://github.com/jump-cellpainting/JUMP-MOA): plate composition,
  within-plate repetitions and annotation caveats.
- [JUMP Hub data description](https://github.com/broadinstitute/jump_hub/blob/main/explanations/data_description.md):
  production/pilot scope, pooled CRISPR guides and cross-site compound sampling.
- [JUMP scope analysis](https://github.com/jump-cellpainting/jump-scope-analysis):
  imaging-system robustness context.

These are source descriptions, not evidence that this project has executed or
validated the listed external experiments.
