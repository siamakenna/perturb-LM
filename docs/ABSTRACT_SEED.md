# Abstract Seed

This is a living research abstract seed for external scientific writing. It is not a handoff document and should not be read as reporting completed model results.

## Working Titles

1. Perturb-LM: Leakage-Aware Language Retrieval of Cell Painting Morphology
2. Evaluating Biomedical Language Alignment Against Cell Painting Morphology Profiles
3. A Leakage-Aware Benchmark for Natural-Language Perturbation Retrieval in Cell Painting Screens

Preferred title:

> Perturb-LM: Leakage-Aware Language Retrieval of Cell Painting Morphology

## One-Sentence Problem Statement

High-content microscopy screens contain rich perturbation-induced phenotypes, but those phenotypes are difficult to search using natural-language biological concepts without introducing evaluation leakage.

## One-Sentence Hypothesis

Frozen biomedical language representations contain enough mechanistic information to support retrieval of perturbation-induced morphology after lightweight alignment, but success must be demonstrated against identifier-stripped lexical controls under held-out and leakage-aware evaluation.

## Contributions

1. **Benchmark:** A perturbation-level, leakage-aware text-to-morphology retrieval task for Cell Painting profiles.
2. **Method:** Lightweight alignment of frozen biomedical language representations to morphology-profile space, currently planned as the next experiment.
3. **Evaluation:** Held-out and leakage-aware evaluation using lexical, random, shuffled-label, replicate, plate, well, and eventually batch controls.

## Working Abstract

Cell Painting screens provide high-dimensional profiles of perturbation-induced cellular morphology, but searching these profiles with natural-language biological concepts remains difficult to evaluate rigorously. Naive retrieval benchmarks can be inflated by treatment identifiers, target sequences, replicate structure, plate effects, well-position effects, and batch-specific artifacts. We introduce Perturb-LM, a leakage-aware benchmark foundation for aligning biomedical language with Cell Painting morphology profiles. The current system validates 4,524 JUMP CPJUMP1 profiles in a consistent 904-feature morphology space, constructs 641 full-query lexical benchmark queries, removes direct identifiers from the primary lexical control, and reports perturbation-level retrieval metrics with query-level uncertainty. Identifier-stripped TF-IDF achieves mAP 0.2513 with a 95% query-bootstrap confidence interval of 0.2445 to 0.2582, establishing a strong lexical baseline rather than a learned-model result. The next experiment will freeze a biomedical text encoder and train a lightweight projection into morphology-profile space, testing whether aligned language representations outperform identifier-stripped lexical controls under held-out plate, held-out treatment, and leakage-aware retrieval filters. [Learned alignment results pending.]

## Current Results That May Be Stated

- 4,524 CPJUMP1 profiles are available in the current local benchmark.
- The primary feature space contains 904 morphology features.
- The full lexical benchmark contains 641 queries.
- Identifier-stripped TF-IDF mAP is 0.2513.
- The mAP 95% query-bootstrap confidence interval is 0.2445 to 0.2582.
- Held-out batch evaluation is currently unavailable.
- Split-specific learned-model results remain pending.

## Placeholder Results

- Frozen text embedding baseline: pending.
- Learned linear projection: pending.
- Held-out plate model evaluation: pending.
- Held-out treatment model evaluation: pending.
- Same-plate and same-well filtered learned-model evaluation: pending.
- Batch-generalization evaluation: pending.
- Image-level retrieval: pending.

## Claim Boundaries

Perturb-LM currently supports claims about reproducible benchmark infrastructure, leakage controls, and lexical baselines. It does not yet establish biological retrieval, batch generalization, image-level retrieval, clinical utility, or superiority of a learned model.
