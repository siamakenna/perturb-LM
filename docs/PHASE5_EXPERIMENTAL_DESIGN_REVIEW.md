# Phase 5 experimental-design review

2026-10-14; related [#30](https://github.com/siamakenna/perturb-LM/issues/30) and [#52](https://github.com/siamakenna/perturb-LM/issues/52). This is a proposed interpretation of the completed [cohort audit](PHASE5_CPJUMP1_COHORT_AUDIT.md), not an approved new benchmark.

## Preserve the design metadata

Exclude batch, plate, well, file names, IDs and acquisition details from predictive text/features. Retain them in a separate evaluation table with cell type, parental/Cas9 status, modality, duration, dose provenance, relative/absolute seeding density, antibiotics, controls and staining/imaging flags. Split membership and sample eligibility depend on those variables. Cell line and modality cannot be substituted for batch.

Only one original source batch is represented. Same-batch neighbors would be 100% by construction; between-batch similarity/variability and held-out-batch generalization are not identifiable. The additional timepoint file is a different acquisition of an ORF plate, not evidence of independent experimental-batch replication; it also falls outside the historical feature/population contract. Expanding to it automatically would not solve this problem.

Plate replication is asymmetric. The local strata have 4 A549 compound plates, 1 U2OS compound plate, 4 U2OS CRISPR plates, 1 A549 CRISPR plate without puromycin, and 2 with puromycin. Compound exposure is 24 h and CRISPR exposure 144 h. All compound plates and all U2OS CRISPR plates carry WGA anomaly labels. Cell-type effects, staining effects, modality and exposure cannot be cleanly disentangled by a pooled comparison.

## Actual descriptive plate diagnostics

The audit computes exhaustive pairwise cosine moments from the existing 904 features, restricted to nonmissing treatment labels and identical recorded conditions (including anomaly and antibiotics). This is descriptive analysis of already normalized/feature-selected profiles, not an independent estimate of raw batch effects or a new benchmark. Pair counts are dependent; no inferential confidence interval or p-value is attached.

For **different-treatment, different-coordinate pairs**:

| Matched stratum | Same-plate pairs | Mean cosine (SD) | Between-plate pairs | Mean cosine (SD) |
| --- | ---: | --- | ---: | --- |
| A549 compound, 24 h, WGA | 203,785 | 0.05574 (0.24154) | 611,355 | 0.04079 (0.22139) |
| U2OS CRISPR, 144 h, WGA | 287,860 | 0.09357 (0.27531) | 863,580 | 0.07369 (0.24709) |
| A549 CRISPR, 144 h, puromycin | 143,930 | 0.14582 (0.28962) | 143,930 | 0.11998 (0.26440) |

Same-plate means and dispersions exceed between-plate values in all three comparable strata. This supports retaining plate-aware diagnostics, not attributing the difference solely to a causal plate effect. Treatment composition and control mix remain possible contributors. The single-plate strata have no corresponding between-plate comparison. All eligible feature vectors were finite and nonzero in this run. Full moments and same-treatment/position strata are in `outputs/phase5/cohort/plate_similarity.csv`.

Same-coordinate treatment replication is strongly entangled with fixed plate layout. Exact-treatment across-plate eligibility drops from 4,190 to 762 rows when same coordinates are excluded, then to 652 when conditions are matched. Only 156 rows/13 non-control CRISPR reagent IDs remain. Controls account for 496 of the latter 652 rows; a pooled result would be heavily influenced by controls. Well-coordinate recovery is a technical-position diagnostic and must not be called biological accuracy.

## Eligibility matrix

“Supported” below means inputs exist for the stated diagnostic; approval is still required for new scored scientific experiments.

| Scientific comparison | Classification | Reason / required change |
| --- | --- | --- |
| Query information/collisions and scoped leakage | Supported now; completed | Uses existing metadata and unchanged renderers |
| Same-versus-between-plate descriptive cosine within conditions | Supported now; completed | Three replicated strata; report dependence and preprocessing |
| Same treatment across plates, same coordinate allowed | Supported now as sensitivity diagnostic | All 641 IDs; cannot separate identity from fixed position |
| Same treatment across plates and coordinates, matched conditions | Supported narrowly; new scoring dependent on approval | 59 IDs; just 13 non-control CRISPR IDs; no non-control compounds |
| Biological exact-treatment recovery across arbitrary compounds | Supported only after profile/layout expansion | Position-diverse independent replicates are missing |
| Well-coordinate recovery | Supported as acquisition diagnostic, approval for scoring | Same modality layouts confound position and treatment; use unrelated-treatment pairs where possible |
| Cross-batch transfer or between-batch variance | Not identifiable | One original batch; repeated imaging is not an independent batch |
| Cell-line transfer as biological generalization | Dependent on approval and better balance | Available A549/U2OS profiles, but anomaly/Cas9/selection/time effects confound interpretation |
| Compound–CRISPR annotated-target recovery | Dependent on scientific approval | Shared annotations exist; unequal time, parental/Cas9, multi-target mappings and controls require rules |
| Time-matched compound–CRISPR comparison | Not identifiable in local cohort | 24 versus 144 h; source durations differ by modality too |
| ORF-related target recovery | Supported only after metadata/profile expansion | Zero ORF rows in selected cohort |
| Representation-specific biological advantage | Supported only after annotation/representation expansion and approval | Historical comparator evidence exists, but no approved Phase 5 independent biological endpoint |
| Blinded ROI validation | Supported only after exact image mapping | No generated image pairs or fabricated labels |

## Experimental protections to approve

Keep controls separate from the non-control primary population; use them for QC and null contrasts, not to inflate treatment recovery. Distinguish reagent-level identities from gene-level hypotheses. Preserve multiple compound targets and independent guide identities; do not collapse knockout, overexpression and drug effects into one phenotype. Resolve principal-target versus expanded-target discrepancies before choosing positives. Group aliases/related compounds and all relevant guides together when target generalization is claimed.

A future split must leave both query and positive gallery measurements in distinct plates and positions; filtering must occur before aggregation. Hold out treatment or gene groups according to the question, and use training-only fitting for transformations and alignment. The supplied profiles already underwent source normalization/feature selection: a new train-only scaler cannot undo preprocessing performed across the source batch. An inductive claim needs an audit of that upstream fit scope or a reviewed less-processed profile input.

Estimate uncertainty over treatment/gene groups, report plate-specific sensitivity, and expose evaluable/excluded counts per condition. With 13 non-control reagent IDs, uncertainty and selection bias are central. Do not choose a promising subset after inspecting retrieval scores. Approve the estimand and minimum independent units before running models.
