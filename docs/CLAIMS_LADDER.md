# Claims Ladder

Perturb-LM should only make claims that the current evidence supports. This ladder separates established engineering and benchmark facts from the biological claims that still require stronger evidence.

## Established Now

- The software and benchmark pipeline are reproducible on synthetic tests and local aggregate workflows.
- The original local CPJUMP1 profile subset has a consistent 904-feature schema.
- Direct identifier leakage is explicitly controlled.
- Target sequences are prohibited from identifier-stripped query and candidate text.
- Lexical, random, and shuffled-label baselines run across the full query set.
- Query-level uncertainty and evaluable-query counts are reported.
- The current active benchmark is text-to-morphology-profile retrieval.

Allowed claim:

> Perturb-LM provides a reproducible, leakage-aware benchmark foundation for text-to-morphology-profile retrieval on CPJUMP1 profiles.

## Testable Next

- Frozen text embeddings carry useful morphology-relevant information.
- Linear alignment improves retrieval over identifier-stripped TF-IDF.
- Gains persist under held-out plate and held-out treatment conditions.
- Gains persist after same-plate and same-well retrieval filtering.
- Replicate-consensus morphology profiles improve robustness.
- The Phase 3C synthetic smoke validates the alignment contract, but it is not biological evidence.

Allowed future claim, if supported:

> A frozen biomedical text representation with lightweight alignment improves over identifier-stripped lexical controls under the specified held-out evaluation.

## Requires Stronger Evidence

- Pathway-level biological retrieval.
- Generalization across batches.
- Image-level retrieval.
- Performance on other Cell Painting datasets.
- Retrieval of biologically related perturbations beyond exact-label matching.
- External validation with accepted biological annotations.

## Prohibited Current Claims

- Broad biological understanding.
- Clinical utility.
- Causal mechanism discovery.
- Batch-generalized performance.
- Validated natural-language microscopy search.
- Validated text-to-image retrieval.
- Superiority of a learned model before the real experiment runs.
- Biological meaning solely because results are aggregated at the perturbation level.

Current boundary:

> The project is ready to test a learned alignment model, but it has not yet shown biological natural-language retrieval.
