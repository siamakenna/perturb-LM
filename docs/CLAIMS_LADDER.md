# Claims Ladder

This project should make claims only at the level that the current evidence supports.

## Level 0: Software Plumbing

Supported when synthetic fixtures pass:

- parsers run
- manifests validate
- queries build
- retrieval/evaluation scripts complete
- reports generate

Allowed claim:

> The software path runs on tiny fixtures.

Not allowed:

> The model retrieves biology.

## Level 1: Real-Data Asset Readiness

Supported when local audits find real metadata, profiles, embeddings, or images and reports show which artifacts were used.

Allowed claim:

> Real local assets can move through the repo without committing data.

Not allowed:

> The retrieval result is biologically meaningful.

## Level 2: Metadata/Profile Control Retrieval

Supported by the current JUMP profile baseline:

- real CPJUMP1 profiles are audited and indexed
- profile-neighbor diagnostics run
- same-treatment retrieval is compared with random and shuffled-label controls
- text-to-profile metadata baselines run
- direct identifier and identifier-stripped controls are separated

Allowed claim:

> Real profile and metadata-control baselines are reproducible and leakage-aware.

Not allowed:

> Natural-language biological retrieval has been demonstrated.

## Level 3: Leakage-Aware Generalization

Supported only after broader splits are run:

- held-out plates
- held-out wells/images
- held-out perturbations
- held-out batches when labels allow
- cross-batch positives measured

Allowed claim:

> Retrieval remains above controls under specified held-out acquisition or perturbation splits.

Not allowed:

> The system understands microscopy images unless image/model baselines are included.

## Level 4: Text-To-Image Or Text-To-Profile Modeling

Supported only after a model beats:

- random controls
- shuffled-label controls
- full metadata TF-IDF
- identifier-stripped metadata TF-IDF
- leakage-aware split baselines

Allowed claim:

> The model improves over metadata controls under leakage-aware evaluation.

Not allowed:

> Biological discovery, unless validated by external biological evidence.

## Level 5: Biological Retrieval Claim

Requires all earlier levels plus:

- independent validation data or accepted biological annotations
- careful negative controls
- held-out perturbation or mechanism evaluation
- reviewable methods and artifacts

Allowed claim:

> Under the specified benchmark, the method retrieves biologically related perturbations beyond metadata and leakage controls.

This is a future target, not the current project state.
