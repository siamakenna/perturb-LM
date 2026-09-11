# Metadata and preprocessing audit framework

Perturb-LM uses a two-axis definition of metadata and pipeline state:

1. **Visibility:** did a model literally receive the field, string, pixel tensor, mask, or feature vector?
2. **Influence:** could the item alter the pixels, objects, features, grouping, candidate set, labels, or scores?

A value can be invisible to the model but still causally influential. A plate identifier may be removed from text yet still control grouping or normalization. A segmentation threshold may never appear in the prompt but can change every downstream morphology feature.

## Causal classes

| Class | Meaning | Examples |
| --- | --- | --- |
| `MODEL_VISIBLE` | Literal model input | biological description, optional cell type, identifiers or SMILES in a metadata-rich prompt |
| `GROUPING_JOIN` | Associates measurements or files | batch, plate, well, site, channel, image location |
| `INPUT_SHAPING` | Changes pixels or detected objects | illumination correction, clipping, bit-depth conversion, segmentation thresholds and masks |
| `DERIVED_REPRESENTATION` | Produces the representation used for retrieval | per-object features, well aggregation, normalization, feature selection, image embeddings |
| `SUPERVISION_LABEL` | Defines positives or biological labels | exact treatment label, expert-reviewed relevance label |
| `EVALUATION_ONLY` | Changes evaluation without entering the encoder | split assignment, candidate exclusion, evaluability rules |
| `AUDIT_ONLY` | Provenance that should not affect biology | source commit, model revision, package versions, checksums |

## CPJUMP1 profile branch

The existing 904-feature benchmark is downstream of a long image-to-profile lineage:

```text
raw 16-bit TIFF
→ plate/well/site/channel association
→ illumination-function generation and correction
→ intensity handling and DNA-specific background correction
→ nucleus, cell, and cytoplasm segmentation
→ per-object measurements
→ single-cell and well aggregation
→ metadata annotation
→ normalization
→ feature selection
→ 904-feature profile
→ split, candidate filtering, relevance, and metrics
```

Thresholds are module-specific parameter sets, not one project-wide scalar. The executable CellProfiler pipeline and its checksum remain the source of truth. Any regenerated masks must be labeled `REGENERATED` rather than presented as original CPJUMP1 artifacts.

## CellCLIP image branch

CellCLIP is a separate raw-image pathway and must not be treated as if it consumed the existing 904-feature CSV profiles:

```text
raw image
→ intensity cutoff and bit-depth conversion
→ channel selection and ordering
→ crop/resize or augmentation
→ image-backbone embeddings
→ cross-channel fusion and image/profile pooling
→ text/image similarity
→ common Perturb-LM evaluator
```

The CellCLIP operation named `illumination_threshold` should be recorded as a high-intensity clipping rule rather than conflated with CellProfiler flat-field illumination correction.

## Minimum lineage key

At image scale, preserve a stable key capable of linking:

```text
batch → plate → well → site → channel → raw file
→ preprocessing artifact → object labels/features → well profile
→ perturbation → query → model run → retrieval result
```

Use source-native identifiers plus a project-generated immutable artifact ID. Filesystem paths alone are not identities.

## Recommended storage scale

Use `TRACE_ALL + AUDIT_MATERIALIZE`:

- inventory and fingerprint the full pipeline globally;
- avoid persisting every intermediate tensor for every image;
- fully materialize raw images, corrections, masks, overlays, features, prompts, scores, and ranks for a prespecified audit subset.

Recommended audit strata are:

- TF-IDF correct / dense model incorrect;
- projection improves rank;
- all methods incorrect;
- strictly nonevaluable.

## Comparator rule

The metadata audit does not authorize changing the benchmark between models. MedCPT, BioLORD, and CellCLIP must be evaluated against a frozen common candidate/filter/relevance contract, with any modality-specific preprocessing recorded as part of the representation adapter.
