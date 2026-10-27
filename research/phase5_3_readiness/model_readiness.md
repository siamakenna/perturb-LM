# ChAda-ViT development readiness and parallel work

Status: **PROPOSED_NOT_IMPLEMENTED**. Prepared 27 October 2026.

The proposed compatibility candidate is ChAda-ViT/16 Moyen, with the author
checkpoint `nicoboou/chadavit16-moyen` to inspect. ChAda-ViT uses DINO-style
self-supervised learning; it is not specifically an extension of DINOv2.
No checkpoint has been pinned, downloaded, integrated or evaluated by this work.
The completed package CI repair does not establish transformer compatibility.

## Scientific purpose

Test whether preserving separate fluorescence channels improves recovery of
reproducible perturbation-associated morphology across different guides, plates
and well positions. Channel acceptance is an engineering result; improved
biological retrieval requires a controlled experiment. Language retrieval is a
subsequent, separate question.

## Parallel task M1: inspect the public model

The bounded public-source audit found two integration requirements: the author
wrapper groups flattened single-channel inputs through `index` and
`list_num_channels`, and the retrieved configuration defaults to returning patch
tokens. Fixed image vectors require explicit CLS output or a frozen pooling rule.
The author development stack also declares NumPy 1.24.3 and Torch 2.0.0; assess an
isolated runtime rather than installing it into the repaired NumPy 2 environment.
Immutable source/configuration binding remains incomplete. Pin and hash exact
source, verify licenses and preprocessing, and review custom loading code before
execution. Compare training studies with the evaluation cohort; unknown overlap
does not establish independence. See `model_public_audit.md` and its JSON ledger.

Completion evidence: a source/checkpoint decision record listing verified facts,
unresolved requirements and the exact configuration proposed for a later run.
Inspection does not authorize a checkpoint download or inference.

## Parallel task M2: establish a matching image cohort

Inventory bounded, selected wells before any bulk transfer. Reconcile raw image
files with plate, canonical well, field, perturbation, guide and independently
resolved gene identities. Record checksums, cell context, treatment conditions,
acquisition identifiers and available culture lineage. Keep missing images,
missing wells and uncertain identities explicit.

The completed cross-guide analyses used 904-feature profiles. Those profiles
cannot reconstruct the five raw fluorescence channels. Previously downloaded
compound sites do not establish image coverage for the CRISPR cohort.

Completion evidence: a local, verified cohort inventory and an aggregate
availability report, with exclusions and blockers. Detailed identities and paths
stay local; no invented measurements or substitute cohort is permitted.

## Parallel task M3: specify and test the input adapter

Use invented images to test verified DNA, ER, RNA, AGP and mitochondrial channel
identities; axes and channel ordering; bit depth and intensity processing;
registration; synchronized cropping and resizing; supported missing-channel
masks; and field-to-well aggregation. Display lookup tables must not alter
numeric inputs implicitly. Fit learned preprocessing only on the declared
reference population; label evaluation-control calibration separately.

Keep every field and crop from a well together during splitting. Equal embedding
dimensions do not establish image-text alignment.

Completion evidence: an explicit input/output contract and passing synthetic
tests. These are software results, not real-image performance or biology.

## Integration task M4: one frozen image experiment

Depends on M1–M3. Select one feasible cohort and compare full-channel input with
a prespecified, supported reduced-channel condition. Hold model family, image
area, preprocessing, aggregation, eligibility and training budget as consistent
as practical. Include matched CellProfiler profiles as a reference. Freeze the
endpoint, candidate sets, exclusions and uncertainty plan before new scoring.
Use perturbation/gene groups and actual experimental blocking; repeated wells
and overlapping plate pairs are not independent biological replications.

Retain the existing inspected groups as development data. Confirmation needs a
separately selected condition or cohort. No execution or improved-performance
claim is established by this specification.

## Later task M5: biological language retrieval

Specify independently sourced annotations, relevance rules, identity exclusions,
query-collision accounting and lexical controls. Preserve CellCLIP as the paired
image-text baseline and MedCPT/BioLORD as historical comparators. A new image
encoder requires separately tested language alignment; historical results remain
frozen.

Primary references: [paper](https://arxiv.org/html/2311.15264v2),
[author code](https://github.com/nicoboou/chadavit),
[checkpoint candidate](https://huggingface.co/nicoboou/chadavit16-moyen).
