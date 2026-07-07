# Evaluation Protocol

This protocol defines what must be reported before Phase 3 model work can support stronger claims.

## Primary Evaluation Question

Can a text-conditioned method retrieve matching or biologically related microscopy/profile entries beyond simple controls, while avoiding acquisition-layout shortcuts?

Current Phase 2 answers only a narrower question:

Can metadata/profile retrieval baselines be reproduced on real local JUMP profiles with leakage-aware diagnostics?

## Primary Unit

The long-term benchmark unit is perturbation-level retrieval after site/image aggregation.

The current JUMP Phase 2 profile track also reports profile-row diagnostics because it is validating local morphology-profile controls before image or alignment models.

## Required Inputs

- local metadata or profile files
- generated inventory report
- generated index metadata
- generated diagnostics summaries
- generated text-to-profile summaries
- generated baseline manifest

Generated artifacts remain under `outputs/` and are not committed.

## Required Baselines

Every Phase 3 candidate model must be compared against:

- random retrieval
- shuffled-label retrieval
- full metadata TF-IDF
- identifier-stripped metadata TF-IDF
- relevant profile-neighbor controls

Beating random alone is not sufficient.

## Required Metrics

Report:

- mean average precision
- hit@1, hit@5, hit@10
- recall@1, recall@5, recall@10 where positives are defined
- number of evaluable queries
- same-batch@K
- same-plate@K
- same-well@K
- same-treatment@K
- cross-batch, cross-plate, and cross-well positive counts

## Required Split/Leakage Conditions

At minimum, evaluate or explicitly mark unavailable:

- unfiltered retrieval
- exclude same plate
- exclude same well
- exclude same plate and well
- held-out plate
- held-out perturbation
- held-out batch when multiple batches exist

## Exclusions

Exclusions are acceptable only when reported with counts:

- queries without positive candidates after filtering
- rows missing treatment labels
- rows missing batch/plate/well labels
- unavailable local raw images or embeddings

Use `n_evaluable_queries` whenever filtered evaluation removes all positives for some queries.

## Success Criteria For Phase 3

A Phase 3 model result is only promising if:

1. It beats random and shuffled-label controls.
2. It beats identifier-stripped metadata TF-IDF under the same query/evaluation setup.
3. It remains above controls under leakage-aware filters or held-out splits.
4. It reports failure cases and non-evaluable counts.
5. It does not train on labels that appear unchanged in held-out evaluation.

## No-Claim Conditions

Do not claim biological retrieval when:

- only synthetic fixtures have passed
- only direct metadata lookup succeeds
- only one batch is available and batch generalization is central to the claim
- leakage diagnostics are missing
- model comparisons omit identifier-stripped metadata controls
- local outputs cannot be regenerated from commands
