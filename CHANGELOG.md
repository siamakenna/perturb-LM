# Changelog



## 2026-09-12

- Completed strict M0 MedCPT, BioLORD-2023, and CellCLIP comparator runs.
- Added a comparator-specific metadata and information-boundary framework.
- Distinguished source-author metadata terminology from Perturb-LM causal-role classifications.
- Recorded CellCLIP M0 WELL_MEAN and WELL_ATTENTION results under the frozen 1,079/180 strict contract.
- Added public-safe aggregate comparator data and figure.
- Kept the metadata-rich CellCLIP `PUBLISHED` prompt as a separate pending secondary ablation.

## 2026-09-11

- Reproduced the strict held-out-plate benchmark with same-plate and same-well retrieval candidates excluded: 1,079 total queries and 180 evaluable queries.
- Recorded identifier-stripped TF-IDF mAP 0.1574, unaligned BiomedBERT mAP 0.0092, and projected BiomedBERT mAP 0.0332.
- Added public-safe aggregate benchmark summaries and figures.
- Recorded immutable MedCPT and BioLORD-2023 revisions and successful offline model validation; comparator performance remains pending.
- Added the metadata and preprocessing audit framework.

All notable public changes to Perturb-LM will be recorded here.

## Unreleased

### Added

- Two-person contribution and governance guidance.
- Security reporting policy and citation metadata.
- Pull-request and structured issue templates.
- Dependency update configuration and agent guardrails.
- Collaborator handoff documentation.

## 0.1.0 — Public Prototype Foundation

- Added the public synthetic research prototype.
- Added passing Python and web continuous integration.
- Documented the validated identifier-stripped TF-IDF baseline.
- Added the bounded Phase 3C frozen biomedical retrieval plan.

Learned biomedical model results remain pending.
