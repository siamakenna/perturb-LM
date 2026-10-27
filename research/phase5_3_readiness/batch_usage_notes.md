# Which new data have actually been used?

As of 27 October 2026, the answer is **yes for bounded profile expansions; no for a new multibatch multichannel-transformer experiment**.

| Data stream | Used? | What that means |
| --- | --- | --- |
| U2OS CRISPR, BR00116996–BR00116999 | Completed profile analysis reported | Original four-plate development context in `2020_11_04_CPJUMP1`. |
| A549 CRISPR, BR00117000 plus BR00117003–BR00117005 | Completed profile analysis reported | Three added plates extend the A549 context. All four remain in the same original CPJUMP1 source batch. 1,535 observed profiles were retained; BR00117005 has 383, with cause of the absent profile unknown. |
| Target1/Target2, source_4 / `2021_07_12_Batch8` | Completed bounded descriptive pilot | Production collection cpg0016 was used: Target2 BR00121428 queries and Target1 BR00123523 gallery, with 147 evaluable selected design labels. This is one batch and one pair, not established independent replication. |
| JUMP-MOA / scope acquisitions P1–P4 | Completed exploratory profile studies | Source-label retrieval and a separate post hoc control-centering sensitivity were completed. Acquisition names do not establish culture independence or approved biological positives. |
| Two sites from compound plate BR00117011 | Image preparation and exploratory QC completed | Ten original channel TIFFs produced two five-channel sites. These are not the CRISPR image cohort for the proposed transformer experiment. |
| Broader production batches, additional sources and ORF designs | Investigation/proposal | No further eligible cohort or model execution is established by the current evidence. |
| ChAda-ViT experiment | Proposed, unrun | Architecture recommendation only; checkpoint provenance, input compatibility and a matching image cohort remain to be verified. |

## Evidence boundaries

The original U2OS/A549 and context-diagnostic completions are recorded in the visible handoff and terminal history; their recent raw/result files were not reverified in this audit. Available Batch8, MOA and image-preparation aggregate summaries were inspected in the current workspace and are hash-bound in `batch_usage.json`. Underlying raw profiles and images were not read or transferred.

The latest pasted terminal output verifies PR #93 at `88d367fa7c7ea224af14de979efcb1831d3518d6`, with 15 successful checks, one skipped and no failures or pending checks. This is source publication and software CI, not evidence that a new image model or biological validation ran. No PR merge was performed by the helper.

## What must remain separate

- More plates in a source batch are not additional independent batches.
- Different cell contexts do not isolate a causal cell-type effect.
- A registered batch label does not prove independent culture preparation.
- Public-metadata layout overlap does not establish measured biological replication.
- Numerical morphology profiles cannot reconstruct the original channel images.
- Supporting multiple channel counts does not establish cross-assay biological comparability.
- ChAda-ViT uses DINO-style self-supervised learning, not specifically DINOv2.

## Next evidence-producing task

Build one bounded image availability and channel-mapping inventory for an explicitly selected experimental cohort, alongside guide/identity and preprocessing-provenance reviews. Only after these converge should the compatible image-input path and the controlled full-channel comparison run. Preserve the existing completed analyses as historical development evidence.
