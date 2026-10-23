"""Metadata capacity only: exact reagent versus source-gene/different-sequence (#30,#52).

No query rendering, profile features, scores, fitting, or scientific thresholds.
"""

from __future__ import annotations

import re
from collections import Counter

import pandas as pd

from perturb_lm.audits.cohort import CONDITIONS, clean
from perturb_lm.audits.rotations import PLATES, _validate, canonical_wells, plate_roles

MASKS = ("different_coordinate", "different_row_and_column")
B_LABEL = "provisional_source_gene_string_different_sequence_capacity"


class IdentityError(ValueError):
    """Expose aggregate conflict counts only, never private identities or sequences."""

    def __init__(self, counts):
        super().__init__("Selected identity contradictions; metadata support census stopped")
        self.counts = counts


def sequence(value):
    """Unambiguous nonempty DNA string; no assumed length or efficacy threshold."""
    value = clean(value).upper()
    return value if re.fullmatch(r"[ACGT]+", value) else ""


def gene_string(value):
    """Exact source string, single token; no alias, case or stable-ID resolution."""
    value = clean(value)
    return value if value and not re.search(r"[\s|;,/]", value) else ""


def attach_identities(mapping, annotations):
    """Recheck local and preserved source aliases, even if resolved=true."""
    rows = mapping.copy().map(clean)
    source = annotations[annotations.Perturbation.eq("crispr")].copy().map(clean)
    if source.broad_sample.duplicated().any():
        raise IdentityError(
            {
                "duplicate_source_crispr_reagent_rows": int(
                    source.broad_sample.duplicated(keep=False).sum()
                )
            }
        )
    required = {"gene", "target_sequence", "broad_sample"}
    if not required.issubset(source) or not {
        "Metadata_gene",
        "Metadata_target_sequence",
        "target_sequence",
        "gene",
    }.issubset(rows):
        raise ValueError("Explicit source/local gene and sequence columns required")
    source = source.rename(columns={"gene": "source_gene", "target_sequence": "source_sequence"})
    rows = rows.merge(
        source[["broad_sample", "source_gene", "source_sequence"]],
        on="broad_sample",
        how="left",
        validate="many_to_one",
    ).fillna("")
    crispr = rows.Perturbation.eq("crispr") & rows.broad_sample.ne("")
    selected = rows.Assay_Plate_Barcode.isin(PLATES)
    counts = {}
    conflicts = pd.Series(False, index=rows.index)
    for name, left, right in (
        ("local_source_gene", rows.Metadata_gene, rows.source_gene),
        ("preserved_source_gene", rows.gene, rows.source_gene),
        ("local_source_sequence", rows.Metadata_target_sequence, rows.source_sequence),
        ("preserved_source_sequence", rows.target_sequence, rows.source_sequence),
    ):
        mismatch = crispr & left.ne(right)
        counts[name + "_rows_all_crispr"] = int(mismatch.sum())
        counts[name + "_rows_selected"] = int((mismatch & selected).sum())
        conflicts |= mismatch
    counts["conflict_rows_previously_resolved_true"] = int(
        (conflicts & rows.resolved.str.casefold().isin(["true", "1"])).sum()
    )
    if (conflicts & selected).any():
        raise IdentityError(counts)
    source["valid_sequence"] = source.source_sequence.map(sequence)
    source["single_gene"] = source.source_gene.map(gene_string)
    associations = source[source.valid_sequence.ne("")].groupby("valid_sequence").source_gene
    ambiguous_sequences = set(associations.nunique()[lambda x: x.gt(1)].index)
    rows["valid_sequence"] = rows.source_sequence.map(sequence)
    rows["single_gene"] = rows.source_gene.map(gene_string)
    rows["guide_identity_usable"] = (
        rows.valid_sequence.ne("")
        & rows.single_gene.ne("")
        & ~rows.valid_sequence.isin(ambiguous_sequences)
    )
    counts["source_sequences_with_multiple_gene_strings"] = len(ambiguous_sequences)
    counts["source_sequences_shared_by_multiple_reagent_ids"] = int(
        source[source.valid_sequence.ne("")]
        .groupby("valid_sequence")
        .broad_sample.nunique()
        .gt(1)
        .sum()
    )
    return rows, counts


def units(rows):
    return {
        "wells": len(rows[["Batch", "Assay_Plate_Barcode", "well_position"]].drop_duplicates()),
        "profile_rows": len(rows),
        "reagents": int(rows.broad_sample[rows.broad_sample.ne("")].nunique()),
        "valid_sequences": int(rows.valid_sequence[rows.valid_sequence.ne("")].nunique()),
        "source_gene_strings": int(rows.source_gene[rows.source_gene.ne("")].nunique()),
        "reviewed_stable_genes": 0,
        "plates": int(rows.Assay_Plate_Barcode.nunique()),
        "canonical_coordinates": int(rows.well_position.nunique()),
    }


def training_plate_support(queries, training, plates):
    """Distinguish the union of training IDs from presence on every assigned plate."""
    ids = [set(training.loc[training.Assay_Plate_Barcode.eq(p), "broad_sample"]) for p in plates]
    return {
        "query_wells_seen_on_both_training_plates": sum(
            all(reagent in values for values in ids) for reagent in queries.broad_sample
        ),
        "query_wells_seen_on_either_training_plate": sum(
            any(reagent in values for values in ids) for reagent in queries.broad_sample
        ),
        "both_training_plates_contribute_usable_noncontrol_records": all(bool(s) for s in ids),
    }


def spatial_candidates(gallery, query, mask):
    different = gallery.well_position.ne(query.well_position)
    if mask == "different_row_and_column":
        different = gallery.well_position.str[0].ne(
            query.well_position[0]
        ) & gallery.well_position.str[1:].ne(query.well_position[1:])
    elif mask != "different_coordinate":
        raise ValueError("Unknown spatial sensitivity")
    return gallery[
        different
        & gallery[CONDITIONS].eq(pd.Series({c: getattr(query, c) for c in CONDITIONS})).all(axis=1)
    ]


def endpoint_support(queries, gallery, training, mask, endpoint):
    train_ids = set(training.broad_sample)
    flags, seen_flags, both_seen_flags = [], [], []
    candidate_counts, positive_counts, reagent_counts, sequence_counts = [], [], [], []
    supported_gallery, seen_gallery = set(), set()
    identical_sequence_pairs = 0
    for query in queries.itertuples():
        candidates = spatial_candidates(gallery, query, mask)
        candidate_counts.append(len(candidates))
        if endpoint == "A_exact_reagent":
            positives = candidates[candidates.broad_sample.eq(query.broad_sample)]
        else:
            same_gene_other_reagent = (
                candidates.broad_sample.ne(query.broad_sample)
                & candidates.source_gene.eq(query.source_gene)
                & candidates.guide_identity_usable
                & bool(query.guide_identity_usable)
            )
            identical_sequence_pairs += int(
                (same_gene_other_reagent & candidates.valid_sequence.eq(query.valid_sequence)).sum()
            )
            positives = candidates[
                same_gene_other_reagent & candidates.valid_sequence.ne(query.valid_sequence)
            ]
        flags.append(not positives.empty)
        seen_flags.append(bool(flags[-1] and query.broad_sample in train_ids))
        both_seen_flags.append(
            bool(seen_flags[-1] and positives.broad_sample.isin(train_ids).any())
        )
        positive_counts.append(len(positives))
        reagent_counts.append(int(positives.broad_sample.nunique()))
        sequence_counts.append(
            int(positives.valid_sequence[positives.valid_sequence.ne("")].nunique())
        )
        supported_gallery.update(positives.record_id)
        if seen_flags[-1]:
            seen_gallery.update(positives.record_id)
    supported = queries.loc[flags]
    seen = queries.loc[seen_flags]

    def hist(counts):
        return dict(sorted(Counter(str(n) for n in counts).items()))

    return {
        "raw_gallery_supported_queries": units(supported),
        "training_supported_seen_query_reagent": units(seen),
        "training_supported_seen_query_and_positive_reagents": units(queries.loc[both_seen_flags]),
        "total_query_wells": len(queries),
        "raw_coverage_fraction": len(supported) / len(queries) if len(queries) else None,
        "seen_query_reagent_coverage_fraction": len(seen) / len(queries) if len(queries) else None,
        "no_positive_query_wells": len(queries) - len(supported),
        "query_reagent_not_seen_in_training_wells": int(
            (~queries.broad_sample.isin(train_ids)).sum()
        ),
        "positive_but_query_reagent_unseen_wells": len(supported) - len(seen),
        "candidate_well_count_histogram": hist(candidate_counts),
        "positive_well_count_histogram": hist(positive_counts),
        "positive_reagent_count_histogram": hist(reagent_counts),
        "positive_valid_sequence_count_histogram": hist(sequence_counts),
        "query_positive_well_pairs": sum(positive_counts),
        "unique_positive_gallery_population": units(
            gallery[gallery.record_id.isin(supported_gallery)]
        ),
        "unique_seen_query_positive_gallery_population": units(
            gallery[gallery.record_id.isin(seen_gallery)]
        ),
        "same_sequence_other_reagent_gene_pairs_rejected_for_B": identical_sequence_pairs,
    }


def support_census(mapping, annotations):
    identities, conflicts = attach_identities(mapping, annotations)
    # Preserve all checks in the merged planner, including canonical wells and physical identity.
    selected = _validate(identities)
    selected["well_position"] = canonical_wells(selected.well_position)
    if "Number_of_images" in selected and selected.Number_of_images.nunique() != 1:
        raise ValueError("Selected plates contain mixed recorded imaging conditions")
    # _validate stringifies values. Explicitly restore this derived boolean.
    selected["guide_identity_usable"] = selected.guide_identity_usable.eq("True")
    labeled = selected.broad_sample.ne("")
    usable = selected[labeled & ~selected.is_control].copy()
    result = {
        "status": "DESCRIPTIVE_METADATA_ONLY_NOT_SCIENTIFIC_APPROVAL",
        "execution_allowed": False,
        "minimum_thresholds": None,
        "endpoint_B_label": B_LABEL,
        "stable_gene_review_status": (
            "not_supplied; zero reviewed stable genes is not zero biological genes"
        ),
        "sequence_rule": (
            "Trim, uppercase, nonempty A/C/G/T only; no length, targeting or efficacy assertion"
        ),
        "gene_rule": (
            "Exact source string, single token without whitespace or | ; , /; no "
            "stable-ID or alias resolution"
        ),
        "training_support_rule": (
            "Query reagent present on remaining two matched training plates; no fit; "
            "extra stricter both-reagents count reported separately"
        ),
        "conditions": {c: selected.iloc[0][c] for c in CONDITIONS},
        "recorded_Number_of_images": (
            selected.iloc[0].Number_of_images if "Number_of_images" in selected else "unknown"
        ),
        "input_rows": len(mapping),
        "selected_rows": len(selected),
        "out_of_scope_rows": len(mapping) - len(selected),
        "selected_noncontrol_population": units(usable),
        "selected_missing_label_rows": int((~labeled).sum()),
        "selected_control_rows_with_labels": int((labeled & selected.is_control).sum()),
        "noncontrol_rows_missing_or_invalid_sequence": int(usable.valid_sequence.eq("").sum()),
        "noncontrol_rows_missing_or_ambiguous_gene_string": int(usable.single_gene.eq("").sum()),
        "noncontrol_rows_not_eligible_for_B_identity": int((~usable.guide_identity_usable).sum()),
        "noncontrol_sequence_length_histogram": dict(
            sorted(Counter(str(len(s)) for s in usable.valid_sequence if s).items())
        ),
        "identity_checks": conflicts,
        "assignments_are_independent_experiments": False,
        "assignments": [],
    }
    for q, g, t in plate_roles():
        role_rows = {
            "query": selected[selected.Assay_Plate_Barcode.eq(q)],
            "gallery": selected[selected.Assay_Plate_Barcode.eq(g)],
            "training": selected[selected.Assay_Plate_Barcode.isin(t)],
        }
        roles = {k: v[v.broad_sample.ne("") & ~v.is_control] for k, v in role_rows.items()}
        result["assignments"].append(
            {
                "query_plate": q,
                "gallery_plate": g,
                "training_plates": t,
                "populations": {k: units(v) for k, v in roles.items()},
                "role_exclusions": {
                    k: {
                        "input_rows": len(v),
                        "missing_label_rows": int(v.broad_sample.eq("").sum()),
                        "labeled_control_rows": int((v.broad_sample.ne("") & v.is_control).sum()),
                    }
                    for k, v in role_rows.items()
                },
                "training_plates_with_noncontrol_rows": roles[
                    "training"
                ].Assay_Plate_Barcode.nunique(),
                "per_training_plate_usable_population": {
                    p: units(roles["training"][roles["training"].Assay_Plate_Barcode.eq(p)])
                    for p in t
                },
                "explicit_both_training_plate_support": training_plate_support(
                    roles["query"], roles["training"], t
                ),
                "spatial_masks": {
                    mask: {
                        endpoint: endpoint_support(
                            roles["query"], roles["gallery"], roles["training"], mask, endpoint
                        )
                        for endpoint in (
                            "A_exact_reagent",
                            "B_different_reagent_sequence_same_source_gene",
                        )
                    }
                    for mask in MASKS
                },
            }
        )
    return result
