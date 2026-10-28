# Phase 5.3 A549 exploratory context extension (#30, #52)

This is a separate four-plate A549 analysis selected after the completed U2OS
exploratory study. The user authorized independent exploratory development on
26 October 2026. No coauthor or biological-identity approval is asserted.

## The scientific question

Does the same source-annotated, different-recorded-guide morphology contrast
remain observable in a second recorded cell context? A549 is analyzed on its
own matched-condition plates. U2OS profiles are not rescored or pooled with it.
All native eligible A549 groups are included; none are selected using favorable
U2OS gene names or A549 feature values. The primary endpoint, spatial masks,
reference weighting, complete-pair weighting, ambiguity holds, feature values
and QC rules remain the same as the completed U2OS implementation.

This is a same-batch context extension, not an untouched independent-batch
validation. Recorded cell context and anomaly/staining fields differ between
arms, so their differences do not isolate a cell-type or WGA intervention.
Guide efficacy, stable target identity and independent culture lineage remain
unreviewed. Source-batch feature selection/preprocessing remains explicit.
Any later direct cross-context comparison must check ordered feature-schema
hashes and use shared recorded-gene/guide groups; this arm reports native A549
results and does not generate a causal cross-context comparison.

## Fixed inputs and conditions

The only selected plates are BR00117000, BR00117003, BR00117004 and BR00117005.
The pinned public experiment table records CRISPR, A549/Cas9, 144 hours,
density 100, antibiotics absent, Day0, first imaging and anomaly none. Plates
BR00117001 and BR00117002 are excluded because their antibiotic condition is
puromycin. The runner verifies source bytes and actual joined rows before
numeric conversion. Image counts are not used as profile-row or well counts.

[Source experiment table](https://raw.githubusercontent.com/jump-cellpainting/2024_Chandrasekaran_NatureMethods_CPJUMP1/56845c7d4dc322652952783d91dae0ffef47829f/benchmark/output/experiment-metadata.tsv)

The physical design has 1,536 positions (384 per plate), but available profile
rows are not assumed to fill every position. Each of the four pinned files must
contain 1–384 unique, valid physical wells and the same 904 unchanged ordered
features. Every observed row is retained. The selected files are the four
`normalized_feature_select_negcon_batch` profiles at source revision
`56845c7d4dc322652952783d91dae0ffef47829f`. Actual row counts, ordered schema
and source metadata are verified from the complete hash-bound capture. The A549 counts and results are not established
by this source-only correction. Missing
objects, contradictory conditions or a different schema stop the run; no
substitute, imputation, revised eligibility or favorable cohort is selected.

Bounds remain 16 MiB compressed per profile and 64 MiB total, 32 MiB decompressed
per profile and 1 MiB per source metadata file. No images, private profiles,
models, bulk production datasets or Biowulf resources enter this study.
The independent U2OS validator is not modified or monkeypatched.

## Resume the stopped v1 run in the existing checkout

The transfer kit's `repair-and-resume.py --work EXISTING_WORK --publish --execute`
uses the existing authenticated Mac checkout and preserved input capture. It
verifies the original PR #92 head, frozen source and capture binding, performs
the metadata-only census, tests and commits only the eight reviewed source/doc/
test corrections, and verifies the push to that same PR before offline analysis.
The transfer helper itself is not repository code. It does not clone another
checkout, create another research branch/PR, redownload profiles or overwrite
the stopped run. Source and test changes are committed before numeric scoring.

Existing U2OS results stay unchanged. No PR is merged and no research output is
automatically published. The helper reuses the existing numerical environment.
Source changes or an advanced PR head stop for review rather than being forced.

The amended v2 analysis freezes the protocol before inspection and binds a
metadata-only census before numeric feature conversion or scoring. Source CSV
feature fields are necessarily parsed as strings while auditing metadata. Cross-guide/position
comparisons and the query-field information audit run as two concurrent local
CPU tasks. The scoring engine and query audit are byte-identical to the completed U2OS
versions. The report adds explicit observed-versus-planned availability and
unknown-missingness caveats. They are complementary analyses of one A549 cohort,
not separate biological replications.

Outputs are ignored local `outputs/phase53-a549.*` directories containing
`summary.json`, `report.html`, five figures, `report.pdf`, provenance and hash
receipts. Detailed source-identity tables stay in `PRIVATE/`. Completion means
computation/report completion, not reviewed biology. Empty eligibility remains
unavailable with explicit coverage. Return only the aggregate `summary.json`
for interpretation; current GitHub CI should be assessed on the new source head.

## Reproduce from the published checkout

Use a clean committed checkout and Python 3.10–3.12 with NumPy, pandas and
Matplotlib. From the repository root:

```bash
export PYTHONPATH="$PWD/src"
export PYTHONDONTWRITEBYTECODE=1 MPLBACKEND=Agg
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
python -m unittest discover -s research/phase5_3_a549 -p 'test_*.py' -v
python research/phase5_3_a549/run_analysis.py \
  --repo "$PWD" --out "$PWD/outputs/phase53-a549-NEW" \
  --staging /path/to/preserved/inputs \
  --preflight-census /path/to/verified/preflight-census.json \
  --authorize-exploratory
```

Use the preflight census generated by the recovery helper and a fresh ignored
output directory. The staged command reuses the verified source bytes offline.
No model training or pretrained inference
is part of this command. Read `PROTOCOL.json` for the frozen experimental rules.
`REPLICATION_PLAN.md` specifies the parallel metadata-first external compound
holdout task and its present selected-well-data acquisition blocker.

## Correction of the stopped v1 capture

The v1 study stopped before scoring because it incorrectly equated physical
plate capacity with the number of available profile rows. This v2 amendment
preserves the stopped run and original captured bytes. It keeps the same four
plates, 904-feature schema, conditions, endpoint, masks, weights, identity holds
and vector-QC policy. It does not fill absent wells, drop additional observed
rows, choose favorable genes or treat absent profiles as zero effects.

`public_inputs.preflight_capture(staging)` verifies the complete captured files
and their LFS/source hashes, validates physical identities and annotations, and
returns a JSON-safe census before numeric conversion. It reports actual rows
per plate, observed versus 1,536 physical positions, missingness by source role
and control class, and planned versus observed reagent/gene-string/sequence
representation. Entirely absent source gene groups remain in planned counts.
Unknown design annotations remain unclassified, not validated treatments.

`run_analysis.py --staging EXISTING_INPUTS --preflight-census CENSUS_JSON` checks
the supplied census against a fresh metadata-only census, freezes those exact
counts and hashes, and then converts all observed feature rows. Its fresh
output contains `preflight-census.json`, the amended frozen contract and a
`PRIVATE/planned-well-availability.csv` ledger. Original inputs and prior
outputs are unchanged. No network request is needed in this staged path.

The ranking/contrast denominator remains observed profiles and complete eligible
guide support. It is not the complete physical grid. Full-grid availability and
planned source-annotation representation are reported separately. Absence causes
are **unknown**: no automatic claim of QC exclusion, cell death, missing-at-random
sampling or unbiased biological coverage is supported. Results remain a
conditional exploratory source-annotation description.

Input failures now write a local-only `input-error-PRIVATE.json` with the actual
exception and short code locations. Keep that diagnostic local unless reviewed.
No new coauthor approval, biological validation, inference or independent culture
claim is introduced by this engineering correction.
