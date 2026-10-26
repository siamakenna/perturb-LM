"""Distinct, provisional source-string cross-guide endpoint on supplied vectors.

No target/guide/biology validation is inferred, and no reviewed audit gate is
overridden. Upstream vector fitting is unverified. This module never fits a
transform, selects features, imputes, tests a hypothesis, or creates intervals.
The only imported design operation is the canonical metadata weight contract.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from itertools import combinations, permutations

import numpy as np
import pandas as pd

from perturb_lm.audits.cross_guide_design import balanced_comparison_weights
from perturb_lm.audits.rotations import canonical_wells


MASKS = ("different_row_and_column", "different_coordinate")
ENDPOINT = "provisional_recorded_source_gene_different_DNA_string_cosine_contrast"
REQUIRED = {
    "row_id", "plate", "well", "gene", "reagent", "sequence", "condition",
    "treatment", "control", "pert_type", "control_type", "negcon_control_type",
}
RELATIONS = (
    "excluded_condition", "excluded_position", "excluded_exact_reagent",
    "excluded_identical_DNA_string", "excluded_reverse_complement_DNA_string",
    "unlabeled", "provisional_same_source_gene_other_DNA_string",
    "provisional_other_source_gene_reference",
)
UNKNOWN = {"", "na", "n/a", "nan", "none", "null", "unknown", "unannotated"}
OBS_COLUMNS = [
    "mask", "row_id", "gene", "guide", "partner_guide", "anchor_plate",
    "gallery_plate", "well", "positive_mean_cosine", "reference_mean_cosine",
    "contrast", "position_positive_mean", "position_reference_mean", "position_contrast",
    "positive_wells", "reference_wells", "reference_guides",
    "reference_genes", "weight", "complete_pair_eligible",
]
ANCHOR_COLUMNS = [
    "mask", "row_id", "gene", "guide", "anchor_plate", "gallery_plate", "well",
    "source_gene_status", "label_usable", "vector_status", "base_gallery_records",
    "metadata_positive_wells", "metadata_reference_wells", "finite_positive_wells",
    "finite_reference_wells", "has_positive_and_reference", *RELATIONS,
]
GENE_COLUMNS = [
    "mask", "gene", "source_gene_status", "initial_anchor_wells",
    "initial_sequence_guides", "initial_plates", "finite_anchor_wells",
    "label_usable_anchor_wells", "no_metadata_positive_anchor_gallery_comparisons",
    "no_metadata_reference_anchor_gallery_comparisons", "complete_guide_pairs",
    "contrast", "position_contrast", "complete_pair_eligible", "weight",
]


def _clean(value):
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _boolean(value, field):
    text = _clean(value).casefold()
    if text in {"true", "1"}:
        return True
    if text in {"false", "0"}:
        return False
    raise ValueError(f"{field} requires explicit bool/true/false/1/0")


def _gene_reason(gene):
    if gene.casefold() in UNKNOWN:
        return "unknown_or_missing_source_gene"
    if re.fullmatch(r"[A-Pa-p]0?(?:[1-9]|1[0-9]|2[0-4])", gene):
        return "unresolved_well_like_source_gene_identifier_ambiguity"
    if re.search(r"[\s|;,/]", gene):
        return "unresolved_multitoken_source_gene_string"
    return "usable_recorded_source_gene_string_only"


def _sequence(value):
    value = _clean(value).upper()
    return value if re.fullmatch(r"[ACGT]+", value) else ""


def _revcomp(value):
    return value.translate(str.maketrans("ACGT", "TGCA"))[::-1]


def _prepare(metadata, features):
    if not isinstance(metadata, pd.DataFrame) or metadata.columns.duplicated().any():
        raise ValueError("Metadata must have unique named columns")
    if REQUIRED - set(metadata):
        raise ValueError("Missing required metadata columns: " + ", ".join(sorted(REQUIRED - set(metadata))))
    try:
        values = np.asarray(features, dtype=np.float64)
    except (ValueError, TypeError) as exc:
        raise ValueError("Features must be a numeric two-dimensional array") from exc
    if values.ndim != 2 or values.shape[0] != len(metadata) or values.shape[1] == 0:
        raise ValueError("Features must have one aligned row per metadata row and at least one column")
    rows = metadata.copy().reset_index(drop=True)
    for field in REQUIRED - {"treatment", "control"}:
        rows[field] = rows[field].map(_clean)
    for field in ("row_id", "plate", "well", "condition"):
        if rows[field].eq("").any():
            raise ValueError(f"Missing physical/condition metadata: {field}")
    if rows.row_id.duplicated().any():
        raise ValueError("Duplicate row_id")
    if rows.condition.nunique() != 1:
        raise ValueError("Exactly one recorded condition stratum required")
    rows["well"] = canonical_wells(rows.well)
    if not rows.well.str.fullmatch(r"[A-P](?:0[1-9]|1[0-9]|2[0-4])").all():
        raise ValueError("Invalid physical well")
    if rows.duplicated(["plate", "well"]).any():
        raise ValueError("Duplicate physical plate/well")
    plates = sorted(rows.plate.unique())
    if len(plates) != 4:
        raise ValueError("Exactly four distinct physical plates required")
    for field in ("treatment", "control"):
        rows[field] = rows[field].map(lambda x: _boolean(x, field))
    labeled = rows.reagent.ne("")
    if not rows.treatment.eq(labeled & rows.pert_type.eq("trt")).all():
        raise ValueError("Treatment flag contradicts recorded reagent/pert_type")
    if not rows.control.eq(labeled & rows.pert_type.ne("trt")).all():
        raise ValueError("Control flag contradicts recorded reagent/pert_type")
    rows["source_gene_status"] = rows.gene.map(_gene_reason)
    rows["valid_DNA_string"] = rows.sequence.map(_sequence)
    rows["guide"] = rows.valid_DNA_string.map(
        lambda x: "seq_sha256:" + hashlib.sha256(x.encode("ascii")).hexdigest() if x else ""
    )
    # Contradictory recorded reagent identity is an input error, never replication.
    for _, group in rows[labeled].groupby("reagent", sort=True):
        if (group.gene.nunique() > 1 or group.sequence.str.upper().nunique() > 1
                or group.treatment.nunique() > 1 or group.control.nunique() > 1):
            raise ValueError("Recorded reagent identity contradicts source gene, DNA string, or treatment/control role")
    associations = rows[rows.treatment & rows.valid_DNA_string.ne("")].groupby("valid_DNA_string").gene
    ambiguous_sequences = set(associations.nunique()[lambda x: x.gt(1)].index)
    # Shared sequence annotations do not validate a biological identity. Retain
    # these records in the gallery but do not label either gene relationship.
    rows["sequence_gene_ambiguous"] = rows.valid_DNA_string.isin(ambiguous_sequences)
    rows["label_usable"] = (
        rows.source_gene_status.eq("usable_recorded_source_gene_string_only")
        & rows.valid_DNA_string.ne("") & ~rows.sequence_gene_ambiguous
    )
    finite = np.isfinite(values).all(axis=1)
    scale = np.zeros(len(rows), dtype=float)
    scale[finite] = np.max(np.abs(values[finite]), axis=1)
    valid = finite & (scale > 0)
    unit = np.zeros_like(values)
    # Scale first: squaring even finite inputs directly can overflow/underflow.
    unit[valid] = values[valid] / scale[valid, None]
    lengths = np.sqrt(np.sum(unit[valid] ** 2, axis=1))
    unit[valid] /= lengths[:, None]
    rows["vector_status"] = np.where(~finite, "nonfinite", np.where(scale > 0, "valid", "zero_norm"))
    rows["vector_valid"] = valid
    # Canonical physical order makes floating reductions and PRIVATE row order
    # deterministic under a jointly shuffled metadata/vector input.
    order = rows.sort_values(["plate", "well", "row_id"]).index.to_numpy()
    rows = rows.loc[order].reset_index(drop=True)
    unit = unit[order]
    return rows, unit, plates


def _labels(anchor, gallery, mask):
    """Provisional recorded-string labels, separate from reviewed audit relation()."""
    labels = np.full(len(gallery), "unlabeled", dtype=object)
    same_condition = gallery.condition.eq(anchor.condition).to_numpy()
    position = gallery.well.eq(anchor.well).to_numpy()
    if mask == "different_row_and_column":
        position |= (gallery.well.str[0].eq(anchor.well[0])
                     | gallery.well.str[1:].eq(anchor.well[1:])).to_numpy()
    remaining = same_condition & ~position
    labels[~same_condition] = "excluded_condition"
    labels[same_condition & position] = "excluded_position"
    exact_reagent = gallery.reagent.eq(anchor.reagent).to_numpy() & bool(anchor.reagent)
    exact_sequence = gallery.valid_DNA_string.eq(anchor.valid_DNA_string).to_numpy() & bool(anchor.valid_DNA_string)
    reverse_sequence = gallery.valid_DNA_string.eq(_revcomp(anchor.valid_DNA_string)).to_numpy() & bool(anchor.valid_DNA_string)
    for excluded, name in (
        (exact_reagent, "excluded_exact_reagent"),
        (exact_sequence, "excluded_identical_DNA_string"),
        (reverse_sequence, "excluded_reverse_complement_DNA_string"),
    ):
        take = remaining & excluded
        labels[take] = name
        remaining &= ~excluded
    usable = remaining & gallery.label_usable.to_numpy() & bool(anchor.label_usable)
    same_gene = gallery.gene.eq(anchor.gene).to_numpy()
    labels[usable & same_gene] = "provisional_same_source_gene_other_DNA_string"
    labels[usable & ~same_gene] = "provisional_other_source_gene_reference"
    return labels


def _finite_mean(values):
    return float(np.mean(values)) if len(values) else None


def _position_similarities(well, gallery_wells):
    """Prespecified 384-well position kernel; no data-dependent bandwidth."""
    row_difference = gallery_wells.str[0].map(ord).to_numpy() - ord(well[0])
    column_difference = gallery_wells.str[1:].astype(int).to_numpy() - int(well[1:])
    return 1.0 - 0.5 * (np.abs(row_difference) / 15.0 + np.abs(column_difference) / 23.0)


def _reference_mean(gallery, labels, cosines):
    take = (labels == "provisional_other_source_gene_reference") & gallery.vector_valid.to_numpy()
    reference = gallery.loc[take, ["gene", "guide"]].copy()
    if reference.empty:
        return None, 0, 0, 0
    reference["cosine"] = cosines[take]
    # Wells within sequence guide, sequence guides within other source gene,
    # then other source genes: each level receives equal total weight.
    guides = reference.groupby(["gene", "guide"], sort=True).cosine.mean()
    genes = guides.groupby(level="gene", sort=True).mean()
    return float(genes.mean()), len(reference), len(guides), len(genes)


def _json_counts(values):
    return {str(k): int(v) for k, v in sorted(Counter(values).items())}


def analyze_crossguide(metadata: pd.DataFrame, features: np.ndarray, *, masks=MASKS) -> dict:
    """Return JSON-safe aggregate summary and explicitly PRIVATE row tables.

    Inputs are position-aligned; input DataFrame index labels are ignored. The
    complete supplied noncontrol population remains the anchor/gallery denominator.
    Invalid vectors have coverage rows and no numerical observation. No-positive
    or no-reference effects are unavailable (None in summary, NaN in PRIVATE tables).
    """
    masks = tuple(masks)
    if not masks or len(set(masks)) != len(masks) or set(masks) - set(MASKS):
        raise ValueError("Provide distinct supported spatial masks")
    rows, unit, plates = _prepare(metadata, features)
    selected = rows[rows.treatment].copy()
    all_genes = sorted(selected.gene.unique())
    observations, anchor_rows = [], []
    design_results = {}
    aggregate_masks = {}
    private_gene_rows, private_pair_rows, private_direction_rows = [], [], []
    gene_effects, position_gene_effects, pair_sets = {}, {}, {}
    # One numerical cosine matrix for both masks; no fitting or feature selection.
    selection_positions = selected.index.to_numpy()
    cosine = np.clip(unit[selection_positions] @ unit[selection_positions].T, -1.0, 1.0)
    selected["cosine_position"] = np.arange(len(selected))
    for mask in masks:
        current, coverage_rows = [], []
        for p, q in permutations(plates, 2):
            gallery = selected[selected.plate.eq(q)]
            gallery_positions = gallery.cosine_position.to_numpy()
            for anchor in selected[selected.plate.eq(p)].itertuples():
                labels = _labels(anchor, gallery, mask)
                counts = Counter(labels)
                raw_pos = labels == "provisional_same_source_gene_other_DNA_string"
                raw_ref = labels == "provisional_other_source_gene_reference"
                pos = raw_pos & gallery.vector_valid.to_numpy()
                ref = raw_ref & gallery.vector_valid.to_numpy()
                cosines = cosine[anchor.cosine_position, gallery_positions]
                positions = _position_similarities(anchor.well, gallery.well)
                reference, ref_wells, ref_guides, ref_genes = _reference_mean(gallery, labels, cosines)
                position_reference, _, _, _ = _reference_mean(gallery, labels, positions)
                anchor_ok = bool(anchor.vector_valid)
                coverage = {
                    "mask": mask, "row_id": anchor.row_id, "gene": anchor.gene,
                    "guide": anchor.guide, "anchor_plate": p, "gallery_plate": q,
                    "well": anchor.well, "source_gene_status": anchor.source_gene_status,
                    "label_usable": bool(anchor.label_usable), "vector_status": anchor.vector_status,
                    "base_gallery_records": len(gallery), "metadata_positive_wells": int(raw_pos.sum()),
                    "metadata_reference_wells": int(raw_ref.sum()),
                    "finite_positive_wells": int(pos.sum()), "finite_reference_wells": int(ref.sum()),
                    "has_positive_and_reference": bool(anchor_ok and pos.any() and ref.any()),
                    **{name: int(counts[name]) for name in RELATIONS},
                }
                coverage_rows.append(coverage)
                if not anchor_ok or reference is None or not pos.any():
                    continue
                positives = gallery.loc[pos, ["guide"]].copy()
                positives["cosine"] = cosines[pos]
                positives["position"] = positions[pos]
                for partner, group in positives.groupby("guide", sort=True):
                    positive = float(group.cosine.mean())
                    current.append({
                        "mask": mask, "row_id": anchor.row_id, "gene": anchor.gene,
                        "guide": anchor.guide, "partner_guide": partner, "anchor_plate": p,
                        "gallery_plate": q, "well": anchor.well,
                        "positive_mean_cosine": positive, "reference_mean_cosine": reference,
                        "contrast": positive - reference,
                        "position_positive_mean": float(group.position.mean()),
                        "position_reference_mean": position_reference,
                        "position_contrast": float(group.position.mean()) - position_reference,
                        "positive_wells": len(group),
                        "reference_wells": ref_wells, "reference_guides": ref_guides,
                        "reference_genes": ref_genes, "weight": 0.0,
                        "complete_pair_eligible": False,
                    })
        frame = pd.DataFrame(current, columns=OBS_COLUMNS)
        cov = pd.DataFrame(coverage_rows)
        records = [tuple(row) for row in frame[["gene", "guide", "partner_guide", "anchor_plate", "gallery_plate", "well"]].itertuples(index=False, name=None)]
        design = balanced_comparison_weights(records, plates)
        weight_map = dict(design["weights"])
        if len(frame):
            frame["weight"] = [weight_map.get(record, 0.0) for record in records]
            frame["complete_pair_eligible"] = frame.weight.gt(0)
        eligible = frame.loc[frame.complete_pair_eligible.astype(bool)].copy()
        total_weight = float(eligible.weight.sum())
        effect = float(np.dot(eligible.weight, eligible.contrast)) if total_weight else None
        position_effect = float(np.dot(eligible.weight, eligible.position_contrast)) if total_weight else None
        if total_weight and not np.isclose(total_weight, 1.0, rtol=1e-10, atol=1e-12):
            raise RuntimeError("Canonical comparison weights do not sum to one")
        gene_effects[mask], position_gene_effects[mask], pair_sets[mask] = {}, {}, {}
        for gene in all_genes:
            raw = selected[selected.gene.eq(gene)]
            obs = eligible[eligible.gene.eq(gene)]
            gene_weight = float(obs.weight.sum())
            gene_effect = float(np.dot(obs.weight, obs.contrast) / gene_weight) if gene_weight else None
            position_gene_effect = float(np.dot(obs.weight, obs.position_contrast) / gene_weight) if gene_weight else None
            pairs = {tuple(sorted((r.guide, r.partner_guide))) for r in obs.itertuples()}
            if gene_effect is not None:
                gene_effects[mask][gene] = gene_effect
                position_gene_effects[mask][gene] = position_gene_effect
                pair_sets[mask][gene] = pairs
            gene_cov = cov[cov.gene.eq(gene)] if len(cov) else cov
            private_gene_rows.append({
                "mask": mask, "gene": gene, "source_gene_status": raw.source_gene_status.iloc[0],
                "initial_anchor_wells": len(raw), "initial_sequence_guides": int(raw.guide[raw.guide.ne("")].nunique()),
                "initial_plates": int(raw.plate.nunique()), "finite_anchor_wells": int(raw.vector_valid.sum()),
                "label_usable_anchor_wells": int(raw.label_usable.sum()),
                "no_metadata_positive_anchor_gallery_comparisons": int(gene_cov.metadata_positive_wells.eq(0).sum()) if len(gene_cov) else 0,
                "no_metadata_reference_anchor_gallery_comparisons": int(gene_cov.metadata_reference_wells.eq(0).sum()) if len(gene_cov) else 0,
                "complete_guide_pairs": len(pairs), "contrast": gene_effect,
                "position_contrast": position_gene_effect,
                "complete_pair_eligible": bool(gene_weight), "weight": gene_weight,
            })
        for p, q in combinations(plates, 2):
            obs = eligible[eligible.anchor_plate.isin([p, q]) & eligible.gallery_plate.isin([p, q])]
            coverage = cov[cov.anchor_plate.isin([p, q]) & cov.gallery_plate.isin([p, q])] if len(cov) else cov
            weight = float(obs.weight.sum())
            private_pair_rows.append({
                "mask": mask, "plate_a": p, "plate_b": q,
                "contrast": float(np.dot(obs.weight, obs.contrast) / weight) if weight else None,
                "position_contrast": float(np.dot(obs.weight, obs.position_contrast) / weight) if weight else None,
                "weight": weight, "eligible_observations": len(obs),
                "eligible_gene_groups": int(obs.gene.nunique()),
                "initial_anchor_gallery_comparisons": len(coverage),
                "supported_anchor_gallery_comparisons": int(coverage.has_positive_and_reference.sum()) if len(coverage) else 0,
            })
        for p, q in permutations(plates, 2):
            obs = eligible[eligible.anchor_plate.eq(p) & eligible.gallery_plate.eq(q)]
            coverage = cov[cov.anchor_plate.eq(p) & cov.gallery_plate.eq(q)] if len(cov) else cov
            weight = float(obs.weight.sum())
            private_direction_rows.append({
                "mask": mask, "anchor_plate": p, "gallery_plate": q,
                "contrast": float(np.dot(obs.weight, obs.contrast) / weight) if weight else None,
                "position_contrast": float(np.dot(obs.weight, obs.position_contrast) / weight) if weight else None,
                "weight": weight, "eligible_observations": len(obs),
                "eligible_gene_groups": int(obs.gene.nunique()),
                "initial_anchor_gallery_comparisons": len(coverage),
                "supported_anchor_gallery_comparisons": int(coverage.has_positive_and_reference.sum()) if len(coverage) else 0,
            })
        aggregate_masks[mask] = {
            "contrast": effect, "position_contrast": position_effect,
            "initial_anchor_wells": len(selected),
            "initial_source_gene_groups": len(all_genes),
            "anchor_gallery_comparisons": len(cov),
            "base_gallery_record_comparisons": int(cov.base_gallery_records.sum()) if len(cov) else 0,
            "no_metadata_positive_anchor_gallery_comparisons": int(cov.metadata_positive_wells.eq(0).sum()) if len(cov) else 0,
            "no_metadata_reference_anchor_gallery_comparisons": int(cov.metadata_reference_wells.eq(0).sum()) if len(cov) else 0,
            "finite_supported_anchor_gallery_comparisons": int(cov.has_positive_and_reference.sum()) if len(cov) else 0,
            "input_observations": len(frame), "eligible_observations": len(eligible),
            "eligible_gene_groups": int(design["eligible_gene_groups"]),
            "input_gene_groups_with_numerical_comparisons": int(design["input_gene_groups"]),
            "complete_guide_pairs": int(design["complete_guide_pairs"]),
            "input_guide_pairs": int(design["input_guide_pairs"]),
            "total_weight": total_weight,
            "relation_counts": {name: int(cov[name].sum()) if len(cov) else 0 for name in RELATIONS},
            "unordered_plate_pairs": [{k: v for k, v in row.items() if k != "mask"} for row in private_pair_rows if row["mask"] == mask],
            "ordered_plate_directions": [{k: v for k, v in row.items() if k != "mask"} for row in private_direction_rows if row["mask"] == mask],
        }
        design_results[mask] = {k: v for k, v in design.items() if k != "weights"}
        observations.extend(frame.to_dict("records"))
        anchor_rows.extend(coverage_rows)
    paired = None
    if set(MASKS).issubset(masks):
        first, second = MASKS
        primary, secondary = set(gene_effects[first]), set(gene_effects[second])
        common = sorted(primary & secondary)
        differences = [gene_effects[second][gene] - gene_effects[first][gene] for gene in common]
        position_differences = [position_gene_effects[second][gene] - position_gene_effects[first][gene] for gene in common]
        changed_pairs = sum(pair_sets[first][gene] != pair_sets[second][gene] for gene in common)
        paired = {
            "definition": "secondary_minus_primary_within_gene_then_equal_mean_on_intersection_of_complete_gene_groups",
            "interpretation": "Paired descriptive sensitivity only: positive/reference well and guide composition can change with the spatial mask, even on the same complete-gene intersection. This is not a causal position-effect estimate or a layout-adjusted morphology effect.",
            "contrast_difference": _finite_mean(differences), "intersection_gene_groups": len(common),
            "position_contrast_difference": _finite_mean(position_differences),
            "primary_only_gene_groups": len(primary - secondary), "secondary_only_gene_groups": len(secondary - primary),
            "gene_cohort_composition_changed": primary != secondary,
            "intersection_genes_with_changed_complete_guide_pairs": int(changed_pairs),
            "guide_pair_composition_changed_within_intersection": bool(changed_pairs),
        }
    summary = {
        "status": "EXPLORATORY_PROVISIONAL_UNREVIEWED", "endpoint": ENDPOINT,
        "guide_reviewed": False, "biology_reviewed": False, "upstream_fit_status": "unverified",
        "interpretation": "Descriptive mean for the finite complete source-string cohort only; no independent-culture or validated-target claim.",
        "reverse_complement_policy": "Conservative DNA-string exclusion only; reverse complements are not asserted to be established guide equivalents.",
        "guide_identity": "Identical recorded unambiguous DNA strings collapse reagent aliases; no gene alias or case resolution.",
        "weighting": "Canonical balanced_comparison_weights: equal source-gene groups, complete guide pairs, six physical plate pairs, both plate directions, both guide orientations, anchor wells within each cell.",
        "reference_weighting": "Equal wells within sequence guide, equal sequence guides within other recorded source gene, equal other source genes.",
        "position_comparator": "Prespecified similarity 1 - 0.5 * (absolute row difference / 15 + absolute column difference / 23). Same finite morphology-QC candidates, observations and weights; different kernel scale, no subtraction or adjustment. A positive contrast indicates layout shortcut opportunity, not technical causation; zero does not exclude all confounding.",
        "complete_pair_requirement": "Each qualifying guide pair has finite positive/reference support in both guide orientations on all 12 ordered physical plate pairs.",
        "input_rows_including_controls": len(rows), "feature_columns": int(unit.shape[1]),
        "physical_plates": len(plates), "initial_noncontrol_anchors": len(selected),
        "initial_noncontrol_anchors_per_plate": {p: int(selected.plate.eq(p).sum()) for p in plates},
        "control_rows": int(rows.control.sum()), "unclassified_rows": int((~rows.treatment & ~rows.control).sum()),
        "initial_source_gene_groups_including_missing_value": len(all_genes),
        "source_gene_status_noncontrol_counts": _json_counts(selected.source_gene_status),
        "source_gene_group_status_counts": _json_counts(selected.drop_duplicates("gene").source_gene_status),
        "noncontrol_missing_or_non_DNA_sequence_rows": int(selected.valid_DNA_string.eq("").sum()),
        "noncontrol_sequence_gene_ambiguous_rows": int(selected.sequence_gene_ambiguous.sum()),
        "noncontrol_sequence_groups_with_reagent_aliases": int(selected[selected.guide.ne("")].groupby("guide").reagent.nunique().gt(1).sum()),
        "vector_status_all_rows": _json_counts(rows.vector_status),
        "vector_status_noncontrol_rows": _json_counts(selected.vector_status),
        "controls_qc_only": {"vector_status": _json_counts(rows.loc[rows.control, "vector_status"])},
        "masks": aggregate_masks, "paired_mask_difference": paired,
        "independent_experiments": None, "p_values": None, "confidence_intervals": None,
        "design_contract": design_results,
    }
    return {
        "summary": summary,
        "private_observations": pd.DataFrame(observations, columns=OBS_COLUMNS),
        "private_anchors": pd.DataFrame(anchor_rows, columns=ANCHOR_COLUMNS),
        "private_genes": pd.DataFrame(private_gene_rows, columns=GENE_COLUMNS),
        "private_plate_pairs": pd.DataFrame(private_pair_rows),
        "private_directions": pd.DataFrame(private_direction_rows),
    }
