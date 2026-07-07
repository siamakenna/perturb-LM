# Phase 3 Proposal Template

Fill this out before implementing any Phase 3 model.

## Model Name

`TBD`

## Hypothesis

What should this model retrieve better than metadata/profile controls?

## Input

- query text:
- profile embedding:
- image/site embedding:
- metadata fields used:
- fields explicitly excluded:

## Output

- site/image ranking:
- profile ranking:
- perturbation-level ranking:

## Training Data

- dataset:
- labels:
- positives:
- negatives:
- split policy:

## Evaluation Data

- held-out wells/images:
- held-out plates:
- held-out perturbations:
- held-out batches:
- non-evaluable query handling:

## Required Controls

- random:
- shuffled-label:
- full metadata TF-IDF:
- identifier-stripped metadata TF-IDF:
- profile-neighbor baseline:

## Primary Metric

Choose one primary metric before running the model.

## Secondary Metrics

- mAP:
- hit@K:
- recall@K:
- enrichment over random:
- cross-batch positive behavior:
- cross-plate positive behavior:

## Stop Conditions

Stop or revise the model if:

- it only beats random
- it fails to beat identifier-stripped metadata TF-IDF
- it succeeds only with same-plate or same-well neighbors
- it trains on labels that appear unchanged in held-out evaluation
- the readiness checker fails

## Claim If Successful

Write the strongest allowed claim in advance. Avoid biological discovery language unless independent biological validation is added.

## Claim If Not Successful

Write the honest negative result in advance.
