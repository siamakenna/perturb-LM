Perturb-LM Phase 5.2: one local Batch8 morphology-recovery pilot
Prepared 2026-10-14. This is a standalone diagnostic, not a replacement benchmark.

PURPOSE
Test whether morphology profiles can recover matching design-assigned sample
labels across the two already-downloaded layouts, with production-ID agreement.
This is preparation for language-to-morphology research, not a language model.

WHAT TO DO
1. Verify and unpack the ZIP using the accompanying terminal instructions.
2. Run: bash run-local.sh prepare "$HOME/Downloads/perturb-lm-phase52.LyFrde"
   This creates an isolated environment, runs synthetic tests, checks the existing
   local inputs once, and opens plan/REPORT.html. It does not score real data.
3. Read the cohort counts and proposed protocol in that report.
4. Only if you approve that bounded local diagnostic, run the separate score
   command with the plan SHA256. It runs the whole pilot and opens results/REPORT.html.
   No separate chat confirmation or intermediate JSON upload is necessary.
5. Return only results/pilot-summary.json, optionally retrieval-summary.png.
   Keep cohort_LOCAL.json, per-query_LOCAL.json and fitted-preprocessing_LOCAL.json local.

DEPENDENCIES
The runner uses your existing Python and uv locations, then creates a fresh
virtual environment. Binary packages: NumPy 2.3.5, PyArrow 24.0.0, Matplotlib 3.10.8.
UV_SYSTEM_CERTS=true preserves the previously successful Mac certificate setting.
P52_UV may be set to an alternate installed uv binary if the recorded one moved.
No project editable install, GitHub login, Slurm allocation, or GPU is needed.

FIXED PILOT
Reference/gallery: source_4 / 2021_07_12_Batch8 / BR00123523 (Target1).
Query: same source/batch / BR00121428 (Target2).
Relevance: equal complete design Broad sample ID and equal production JCP ID.
These metadata checks do not independently verify stock delivery or assay conditions.
Exclude controls from either source and all one-to-many or duplicate identity
mappings. Keep all remaining Target1 distractors and count Target2 queries without
positives. Standardized chemical keys never collapse distinct sample identities.
Fit median and 1.4826*MAD on the 64 Target1 DMSO controls only; remove features
whose reference-control MAD is zero/nonfinite. Apply frozen scaling to both plates.
No Target2 values are used to select features, fit parameters or tune choices.
Use the 3,673 Cells_/Cytoplasm_/Nuclei_ fields as a restricted baseline. Image_
fields are excluded by scope, not declared devoid of biological information.
Cosine similarity, canonical same-well exclusion, exact-score tie averaging.
Primary conditional MRR; secondary Recall@1/5/10; full evaluability denominator.
References: uniform-rank mathematical expectations and coordinate-only ranking.
These are descriptive controls, not exchangeability-based hypothesis tests.
Stop on nonfinite/zero transformed eligible profiles or no retained features.
No p-values, independent-plate confidence intervals, pretrained inference or
claims of biological mechanism, culture replication, or pure layout effects.
Upstream preprocessing and exact treatment conditions remain unverified.

APPROVAL AND REPRODUCIBILITY
The score command requires the SHA256 of the plan actually reviewed. Before
scoring, it regenerates preparation and checks the plan, implementation, cohort
and input byte bindings. It refuses to overwrite an existing results directory.
The original research code and data remain intact. Outputs are kept under the
existing repository's ignored outputs folder; do not use git add . for them.
An operator's execution approval does not stand in for Claire/Adam's scientific
review and does not approve a manuscript claim or change frozen contracts.

WHAT HAS BEEN TESTED HERE
See VALIDATION.txt for exact synthetic test results and runtime limitations.
No real Batch8 scoring has been run by the author of this package. The files
needed for that computation are on the user's Mac.

IF A COMMAND FAILS
Do not bypass an input/hash/identity guard or retry with arbitrary replacements.
Keep the printed run folder and share the short error plus preparation.log or
scoring.log as appropriate. Failed scoring is marked INCOMPLETE. Do not interpret
partial metrics from a failed run as a completed result.
