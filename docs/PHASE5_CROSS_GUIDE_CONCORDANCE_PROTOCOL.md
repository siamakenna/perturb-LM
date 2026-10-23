# Profile-only cross-guide concordance protocol

2026-10-20. **PROPOSED_NOT_APPROVED — no scores computed.**
Related issues: [#30](https://github.com/siamakenna/perturb-LM/issues/30),
[#52](https://github.com/siamakenna/perturb-LM/issues/52).
Evidence and provenance: [guide-support closeout](PHASE5_GUIDE_SUPPORT_CLOSEOUT.md) and
[October 22 nomenclature/recipe preparation](PHASE5_2_CROSS_GUIDE_READINESS.md).
October 22 revision: clarify equal guide-pair weights and reject label-renaming nulls;
no scored experiment or biological identity review has been completed.
This proposal is separate from the frozen M0 benchmark and Phase 3C contract.
It authorizes no real-data execution or data acquisition.

## Question and interpretation

Within one matched four-plate U2OS/Cas9 CRISPR condition, do profiles from
independently verified different guides targeting the same reviewed stable gene
show higher concordance than appropriately matched profiles assigned to other
reviewed genes, after excluding same plate, same row and same column?

The effect describes agreement conditional on the observed cells, intervention,
plates, candidate universe and upstream preprocessing. It does not establish
causal mechanisms, efficacy, independent cultures or generalization to new
batches, genes or guide sequences. Different-gene comparisons are references,
not certified biological negatives; related genes may share real morphology.

Prefer an untrained similarity diagnostic: it directly asks whether the available
profiles support a coherent cross-guide relationship and needs no fitted map.
A trained retrieval model would additionally test fitting, memorization and
training information exposure, with all current guide sequences already present
on the other plates. It cannot resolve gene/guide identity uncertainty. Defer
that model until the diagnostic, identity review and a guide-disjoint split are
justified and separately approved. No effect was selected from retrieval scores.

## Population before observing scores

Start from the unchanged, source-verified 12-file cohort and complete original
mapping; select only BR00116996–BR00116999 in the recorded source batch. Keep
all 1,536 selected wells in the flow ledger. Noncontrol means the unchanged
`Metadata_pert_type=trt` rule: 1,040 wells, 247 reagent IDs and 130 source gene
strings. The proposal does not import compounds, A549, ORF or other timepoints.

Match source batch, CRISPR modality, U2OS, Cas9, 144 h, absent antibiotics,
relative density 100, Day0, first imaging and WGA flag. Preserve recorded total
image count and all other acquisition provenance without interpreting it as an
independent sample count. Do not pool different recorded conditions. Density
100 is relative seeding density, not 100 cells/well. Per-well effective dose,
knockout efficiency and independent cell preparations remain unresolved.

The strict provisional candidate population contains 720 unique physical wells
across four plates, 180 reagent IDs, 180 different DNA strings and 90 source gene
strings. This is an upper-bound candidate inventory before independent identity
review and new QC/reference eligibility, not an approved 90-gene sample.
Independently reviewed stable gene and guide identities have not been supplied.

## Identity ledger and exclusions

Before feature inspection, freeze a private, versioned ledger reviewed by Claire
and technically checked by Adam. Record source revision/record, reagent ID,
canonical guide identity and aliases, sequence checksum/equivalence group,
sequence orientation, intended locus and approved species/assembly, stable gene
namespace/version and ID, intervention type, evidence citation, reviewer/date,
confidence and inclusion decision. Keep sequences and row keys private.

Distinct source IDs plus unequal DNA strings are necessary metadata evidence,
but insufficient proof of independent guides. Review clone/library aliases,
strand/reverse-complement interpretations, intended target sites, multigene
assignments and known off-target/efficacy concerns. Do not infer biological
independence from two labels or invent an alignment result. Any genome/reference
acquisition requires separate authorization; none occurs in this protocol work.

Map source gene strings to reviewed stable IDs using a fixed reference version.
Merge confirmed aliases before counting genes; a source string with multiple
plausible stable genes remains ambiguous. Exclude unknown/ambiguous relationships
from labeled same-gene and different-gene comparisons while retaining their
presence in the full gallery and exclusion ledger. Contradictory physical
identity, duplicate physical wells or inconsistent joins stop execution for
correction; they are not silently removed. Missing labels and labeled controls
retain separate flow/QC counts and do not enter the noncontrol primary effect.

A primary gene requires at least two reviewed distinct guide identities with
non-equivalent sequences: this defines cross-guide comparison, not a study-size
or power threshold. Require both guide directions to retain positive and
reference support in every prespecified ordered plate pair for the primary
complete-support population. Use all reviewed qualifying guide pairs if alias
resolution yields more than two guides per gene; equal-weight those guide pairs.
When a gene has more than two guides, freeze eligible guide pairs before scoring;
each retained pair must support both guide directions in all ordered plate pairs.
A gene requires at least one such pair. Report every excluded
gene/reagent/well and the reason. Claire must separately decide the minimum
meaningful independent units and whether culture lineage supports that unit;
synthetic 3/2 software thresholds are not study settings.

## Candidate construction and masks

Retain the entire eligible noncontrol gallery on the other plate, not only the
180 provisionally supported reagents. Before review each plate has 260 wells
spanning 247 reagent IDs. Apply identity/QC/condition decisions consistently and
record how that base population changes; never choose candidates by similarity.

For each anchor well on plate p and gallery plate q:

1. Require p and q to differ physically and match the recorded condition.
2. Require different canonical well rows **and** different canonical columns.
   Use shared Phase 5.1 canonicalization/identity validation. No same-coordinate
   or same-row/column exception is selected after seeing scores.
3. Exclude the anchor's exact canonical guide and all equivalent sequence/alias
   entries from labeled comparison candidates, even under a different reagent
   ID or at another coordinate. Keep their exclusion counts in the base-gallery
   ledger. This guards against exact-guide agreement masquerading as cross-guide
   agreement; the gallery is not restricted to the same-gene subset.
4. A prespecified same-gene relationship requires the same independently reviewed
   stable gene, distinct reviewed guides, distinct non-equivalent sequences and
   compatible CRISPR intervention. Unknown relationships remain unlabeled.
5. Reference comparisons require other reviewed stable gene IDs, the same source
   condition and spatial/QC rules, and the same acceptable intervention class.
   Apply any curator-defined related-family/shared-target or incompatibility
   exclusions using frozen external annotations before scoring. Otherwise retain
   known related genes and describe their possible concordance; do not classify
   every different gene as a verified negative.

Use all qualifying reference genes and balance their contribution by gene, then
by canonical guide and physical well. This avoids overweighting genes with more
reagents or repeated wells. No reference is selected using observed feature
values, retrieval rank, image appearance or a favorable score. Morphology-based
cell-count/toxicity matching could remove the effect of interest; it is not part
of the primary proposal. If such QC criteria are required, approve them using
independent measurements in advance and label the resulting change of estimand.

Review identities for the full reference gallery as well as the 180 candidate
anchor reagents. Unreviewed entries in the 247-reagent base gallery cannot be
quietly promoted to known different-gene references.

Keep zero-positive and zero-reference anchors in the coverage denominator. Their
contrast is unavailable, not zero. Keep unknown relation rows in gallery flow
counts without silently treating them as reference negatives. Report base,
masked, relation-labeled and final-comparison candidate counts separately.

## Transformations, fitting and exposure

Use only the existing versioned CellProfiler feature vectors, with deterministic
cosine similarity as the proposed similarity. Do not fit a scaler, select or
reweight features, perform batch correction, optimize a metric, align text,
train a model or tune a setting against this cohort. Per-vector cosine division
is deterministic normalization, not a learned cross-sample transformation.
Nonfinite or zero-norm profiles have undefined cosine; log and exclude affected
comparisons under a frozen QC policy, without replacing them or relaxing masks.
Their current incidence has not been newly assessed by this closeout.

Execution first needs a reviewed preprocessing interpretation. The preserved
README establishes CellProfiler/Pycytominer processing and normalization variants;
it does not establish the exact fitting population/parameters of these selected
negative-control-normalized, feature-selected artifact bytes. Matching 904
feature names cannot certify train-only processing. If held-out records informed
upstream transforms, interpret the diagnostic conditionally/transductively after
review; if that is unacceptable, pause for separately authorized suitable inputs.
A new scaler does not repair upstream fit exposure.

No training population is used by the primary diagnostic. The other two plates
in the old planner are additional observed plates, not independent test data.
For a later trained method, group all canonical guide/sequence aliases across
roles, audit stable-gene overlap according to its estimand, and forbid exact-guide
exposure to held-out guide evaluation. An absent reagent ID alone is inadequate.
Any tuning and preprocessing must stay within its independently defined training
population. That design requires new review. The F10 guard remains unchanged;
this profile-only proposal generates no predictive text or exception.

## Primary descriptive effect and weighting

For each frozen qualifying unordered guide pair {a,b}, anchor well i from guide
a, and gallery plate q, define:

- P(i,q;a,b): mean cosine to qualifying physical wells of partner guide b, which
  shares the independently reviewed stable gene with a.
- R(i,q;a,b): mean cosine to qualifying different-gene references, averaging wells
  within canonical guide, guides within reference gene, then reference genes equally.
- D(i,q;a,b) = P(i,q;a,b) − R(i,q;a,b). Undefined P or R gives unavailable D and
  explicit coverage loss, not an imputed effect.

Average D over anchor wells within each guide direction a-to-b and b-to-a, then
weight the two directions equally. Weight the two ordered plate orientations
within an unordered physical plate pair equally, and then the six physical plate
pairs equally. Average qualifying unordered guide pairs equally within each
reviewed gene, and finally average eligible genes equally. For exactly two guides
this reduces to the original two-guide proposal. For more guides this explicitly
uses pair weights rather than degree-dependent weighting of anchor guide IDs.
Freeze the reviewed pair/weight table before scoring. Require positive AND
reference support for both guide directions in every ordered plate pair for
each retained guide pair. Report complete-support coverage against all 260
anchor wells per plate and all 130 starting source annotation groups.

The metadata-only `balanced_comparison_weights` helper checks this balancing on
invented observations; it does not supply reviewed identities or feature scores.

The primary quantity is that finite-cohort mean contrast with gene-level and
plate-pair distributions. A positive value alone establishes neither biological
accuracy nor learned-model superiority. No AP, mAP, classifier performance,
benchmark delta or significance threshold is primary here. Exact-reagent support
is a separate population; it cannot serve as a paired relevance-only endpoint
contrast on these data.

## Statistical unit and uncertainty plan

The proposed analysis unit is the reviewed stable-gene cluster, with all its
guides, wells and repeated plate roles retained together. Its suitability as an
independent biological unit is unresolved; guide count and well count do not
establish independent cultures. Report the actual reviewed gene count, guide
count, unique wells, four plates and six physical plate pairs alongside any effect.

Propose 10,000 resamples of gene-level anchor contrasts with replacement, seed
20261020, yielding a 95% percentile interval **conditional on the observed four
plates and frozen reference population**. Reused reference genes create dependence:
this interval describes anchor-gene heterogeneity under that conditioning, not
uncertainty over independent cultures, new plates or the complete reference
population. Adam and Claire must approve the unit, conditioning and minimum
meaningful groups before execution. If those assumptions cannot be justified,
report finite-cohort distributions and plate-pair ranges with the interval
explicitly unavailable; do not attach an unsupported population CI or p-value.

Show all six plate-pair contrasts and the 12 directional coverage tables. Do not
bootstrap wells, guide pairs, rotations or computation seeds as independent
biological replicates. A precise plate-population interval is not supported by
four plates. This is not a power calculation or a future success guarantee.

No randomization test is authorized. Globally renaming gene labels leaves all
same/different pair relationships unchanged and cannot form a null distribution.
Any future randomization must reassign partner relationships under frozen
condition, spatial and guide-multiplicity constraints and justify exchangeability
with reused references and repeated plates. Do not produce a permutation p-value
without that separate contract and review.

## Coverage, failure criteria and sensitivities

Report all initial rows and each exclusion, unique units, reviewed relation
counts, base/masked/reference candidates, positives, no-positive/no-reference
anchors and the complete-support gene population. Report raw metadata capacity
separately from post-review/QC evaluability. No-positive comparisons have no
contrast; they must not disappear from the coverage panel.

Stop before scoring on failed hashes/joins, duplicate wells, unresolved physical
identity, absent gene/guide review, unsupported preprocessing interpretation or
an unapproved design. Stop scored execution if all valid same-gene relationships
or all eligible references disappear. If minimum meaningful units are unmet,
report the shortfall and pause; do not weaken masks, redefine identity, substitute
controls or change the effect after inspecting results. Persist unfavorable or
null effects without choosing another metric or selecting promising genes.

Sensitivity 1: repeat the same approved effect under different-coordinate-only
masking. Report its own coverage, plus the paired change on the intersection of
reviewed complete-support genes between masks. An empty intersection is
unavailable. Mask-specific reference composition may also change; report that
composition and interpret the sensitivity as the combined filtering/reference
change, not a causal estimate of position alone. The preliminary 117-versus-90
source-string counts are not approved
stable-gene denominators.

Sensitivity 2: show directional and physical plate-pair effect/coverage ranges
with frozen identity/reference rules. Those are repeated measurements of this
cohort. A leave-one-plate analysis changes the four-plate design and requires a
separate specification; do not label the 12 role assignments independent trials.

## Execution decision

[Collaborator decisions](PHASE5_CROSS_GUIDE_REVIEW_CHECKLIST.md) must record reviewer,
date, exact protocol revision, private reviewed identity-manifest digest,
preprocessing evidence, structural completeness, effect/weights, uncertainty
choice and unresolved limitations. No approval is prefilled. No trained model,
real-data score, inference, new download, Biowulf workload or publication follows
from this document or the successful metadata tests.
