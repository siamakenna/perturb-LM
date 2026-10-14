"""Plan-only, metadata-based plate rotations for the proposed Phase 5.1 diagnostic.

No fitting, query encoding, scores, or approved benchmark definitions live here (#30, #52).
"""

from __future__ import annotations

import hashlib
import itertools
import json
from collections import Counter

import pandas as pd

from perturb_lm.audits.cohort import BATCH, CONDITIONS, clean

PLATES = tuple(f"BR0011699{i}" for i in range(6, 10))
STATUS = "PROPOSED_NOT_APPROVED"
CONFLICTS = (
    "map_conflict",
    "batch_path_conflict",
    "identity_annotation_conflict",
    "duplicate_plate_well",
)
REQUIRED = (
    "record_id",
    "Batch",
    "Assay_Plate_Barcode",
    "well_position",
    "broad_sample",
    "Metadata_pert_type",
    "Metadata_gene",
    "resolved",
    "experiment_status",
    "barcode_status",
    "well_status",
    "sample_status",
    "annotation_status",
    *CONFLICTS,
    *CONDITIONS,
)
NORMALIZATION_SCOPES = ("unknown", "source_batch_global")


def _boolean(value: object, field: str) -> bool:
    """Do not treat the CSV string 'False' as truthy or accept unknown control flags."""
    text = clean(value).casefold()
    if text in {"true", "1"}:
        return True
    if text in {"false", "0"}:
        return False
    raise ValueError(f"{field} requires explicit true/false or 1/0 values")


def _units(rows: pd.DataFrame) -> dict:
    genes = set(rows.Metadata_gene) - {""}
    return {
        "profile_rows": len(rows),
        "reagents": int(rows.broad_sample.nunique()),
        "gene_annotation_groups": len(genes),
        "rows_missing_gene": int(rows.Metadata_gene.eq("").sum()),
        "reagents_missing_gene": int(rows.loc[rows.Metadata_gene.eq(""), "broad_sample"].nunique()),
        "plates": int(rows.Assay_Plate_Barcode.nunique()),
    }


def _validate(mapping: pd.DataFrame) -> pd.DataFrame:
    if mapping.columns.duplicated().any():
        raise ValueError("Duplicate input column names")
    missing = sorted(set(REQUIRED) - set(mapping.columns))
    if missing:
        raise ValueError(f"Missing mapping columns: {', '.join(missing)}")
    rows = mapping.copy().map(clean)
    for field in ("record_id", "Batch", "Assay_Plate_Barcode", "well_position"):
        if rows[field].eq("").any():
            raise ValueError(f"Missing physical identity field: {field}")
    if rows.record_id.duplicated().any():
        raise ValueError("Duplicate record_id values")
    if rows.duplicated(["Batch", "Assay_Plate_Barcode", "well_position"]).any():
        raise ValueError("Duplicate physical plate/well records")
    selected = rows[rows.Assay_Plate_Barcode.isin(PLATES)].copy()
    if set(selected.Assay_Plate_Barcode) != set(PLATES):
        raise ValueError("All four prespecified U2OS CRISPR plates must be represented")
    if not selected.Batch.eq(BATCH).all():
        raise ValueError("Selected plates have contradictory source batch assignments")
    if not selected.well_position.str.fullmatch(r"[A-P](?:0[1-9]|1[0-9]|2[0-4])").all():
        raise ValueError("Well coordinates must be canonical A01 through P24")
    if selected[CONDITIONS].eq("").any().any():
        raise ValueError("Missing recorded culture/acquisition conditions")
    if len(selected[CONDITIONS].drop_duplicates()) != 1:
        raise ValueError("Selected plates contain mixed culture/acquisition conditions")
    first = selected.iloc[0]
    expected = {
        "Perturbation": "crispr",
        "Cell_type": "u2os",
        "Time": "144",
        "Anomaly": "wga",
        "Density": "100",
        "Time_delay": "day0",
        "Times_imaged": "1",
    }
    if any(first[key].casefold() != value for key, value in expected.items()):
        raise ValueError("Selected rows do not match the proposed U2OS CRISPR 144 h WGA stratum")
    if first.Cell_line.casefold() != "cas9" or first.Antibiotics.casefold() not in {
        "absent", "none"
    }:
        raise ValueError("Selected rows do not match Cas9 / absent-antibiotics conditions")
    if not selected.resolved.map(lambda x: _boolean(x, "resolved")).all():
        raise ValueError("Resolve ambiguous selected mappings before planning")
    for field in CONFLICTS:
        if selected[field].map(lambda x: _boolean(x, field)).any():
            raise ValueError(f"Selected mappings contain {field}")
    for field in ("experiment_status", "barcode_status", "well_status", "sample_status"):
        if not selected[field].eq("matched").all():
            raise ValueError(f"Selected mappings contain ambiguous/nonmatched {field}")
    labeled = selected.broad_sample.ne("")
    if not selected.loc[labeled, "annotation_status"].eq("matched").all():
        raise ValueError("Labeled selected rows require matched annotations")
    if selected.loc[labeled, "Metadata_pert_type"].eq("").any():
        raise ValueError("Labeled selected rows require a treatment/control category")
    # 'trt' is the unchanged audit definition of non-control; never parse booleans by truthiness.
    derived_control = selected.Metadata_pert_type.ne("trt")
    if "is_control" in selected:
        supplied = selected.is_control.map(lambda x: _boolean(x, "is_control"))
        if not supplied.loc[labeled].eq(derived_control.loc[labeled]).all():
            raise ValueError("is_control contradicts the audited treatment/control category")
    selected["is_control"] = derived_control
    for alias, canonical in (
        ("Metadata_broad_sample", "broad_sample"),
        ("mapped_sample", "broad_sample"),
        ("Metadata_Plate", "Assay_Plate_Barcode"),
        ("gene", "Metadata_gene"),
        ("pert_type", "Metadata_pert_type"),
        ("control_type", "Metadata_control_type"),
        ("negcon_control_type", "Metadata_negcon_control_type"),
    ):
        if alias in selected and canonical in selected:
            if not selected[alias].eq(selected[canonical]).all():
                raise ValueError(f"Contradictory selected identity annotation: {alias}")
    if "Metadata_Well" in selected:
        original_wells = selected.Metadata_Well.str.upper().str.replace(
            r"^([A-P])(\d)$", r"\g<1>0\2", regex=True
        )
        if not original_wells.eq(selected.well_position).all():
            raise ValueError("Contradictory selected identity annotation: Metadata_Well")
    for alias in ("Metadata_Batch", "Metadata_batch", "path_batch"):
        if alias in selected and (
            selected[alias].ne("") & selected[alias].ne(selected.Batch)
        ).any():
            raise ValueError(f"Contradictory selected identity annotation: {alias}")
    for _, group in selected[labeled].groupby("broad_sample"):
        if group.Metadata_gene.nunique() > 1 or group.is_control.nunique() > 1:
            raise ValueError("A reagent has inconsistent gene or control annotations")
    return selected.sort_values("record_id").reset_index(drop=True)


def plan_rotations(
    mapping: pd.DataFrame,
    *,
    min_train_groups: int,
    min_evaluable_groups: int,
    upstream_normalization_scope: str,
    split_policy: str = "seen_treatment",
) -> tuple[dict, pd.DataFrame]:
    """Return aggregate proposal and PRIVATE row assignments, never an execution approval.

    The required group thresholds count distinct reagent IDs. They are operator-supplied
    design proposals, not scientific defaults. Gene/treatment-heldout policies fail closed.
    candidate_count/positive_count count rows after masks; corresponding *_reagent_count
    fields count distinct IDs for the proposed subsequent mean_scores_after_filtering.
    """
    for name, value in (
        ("min_train_groups", min_train_groups),
        ("min_evaluable_groups", min_evaluable_groups),
    ):
        if type(value) is not int or value < 1:
            raise ValueError(f"{name} must be an explicit positive integer reagent-group count")
    if split_policy != "seen_treatment":
        raise ValueError(
            "Only seen_treatment is implemented; heldout policies need reviewed grouping rules"
        )
    if upstream_normalization_scope not in NORMALIZATION_SCOPES:
        raise ValueError("Unknown normalization scope; inductive preprocessing cannot be certified")
    rows = _validate(mapping)
    labeled = rows.broad_sample.ne("")
    usable = rows[labeled & ~rows.is_control]
    rotations, assignments = [], []
    for query_plate, gallery_plate in itertools.permutations(PLATES, 2):
        rotation = f"query-{query_plate}__gallery-{gallery_plate}"
        train_plates = sorted(set(PLATES) - {query_plate, gallery_plate})
        training = usable[usable.Assay_Plate_Barcode.isin(train_plates)]
        queries = usable[usable.Assay_Plate_Barcode.eq(query_plate)]
        gallery = usable[usable.Assay_Plate_Barcode.eq(gallery_plate)]
        training_ids = set(training.broad_sample)
        gallery_ids = set(gallery.broad_sample)
        query_ids = set(queries.broad_sample)
        train_genes = set(training.Metadata_gene) - {""}
        query_genes = set(queries.Metadata_gene) - {""}
        gallery_genes = set(gallery.Metadata_gene) - {""}
        evaluation = {}
        for record in queries.itertuples():
            candidates = gallery[gallery.well_position.ne(record.well_position)]
            positives = candidates[candidates.broad_sample.eq(record.broad_sample)]
            reasons = []
            if record.broad_sample not in training_ids:
                reasons.append("reagent_not_seen_in_training")
            if positives.empty:
                reasons.append("no_different_coordinate_positive")
            evaluation[record.record_id] = {
                "evaluable": not reasons,
                "exclusion_reasons": "|".join(reasons),
                "candidate_count": len(candidates),
                "positive_count": len(positives),
                "candidate_reagent_count": int(candidates.broad_sample.nunique()),
                "positive_reagent_count": int(positives.broad_sample.nunique()),
                "positive_record_ids": json.dumps(
                    sorted(positives.record_id), separators=(",", ":")
                ),
            }
        evaluable = queries[
            queries.record_id.map(lambda x: evaluation[x]["evaluable"]).astype(bool)
        ]
        reasons = Counter(
            reason
            for value in evaluation.values()
            for reason in value["exclusion_reasons"].split("|")
            if reason
        )
        gates = []
        empty_training_plates = sorted(set(train_plates) - set(training.Assay_Plate_Barcode))
        if empty_training_plates:
            gates.append("missing_training_plate_population")
        if len(training_ids) < min_train_groups:
            gates.append("insufficient_training_reagent_groups")
        if evaluable.broad_sample.nunique() < min_evaluable_groups:
            gates.append("insufficient_evaluable_reagent_groups")
        if evaluable.empty:
            gates.append("zero_evaluable_queries")
        if gallery.empty:
            gates.append("empty_noncontrol_gallery")
        query_plate_rows = rows.Assay_Plate_Barcode.eq(query_plate)
        count_fields = (
            "candidate_count",
            "positive_count",
            "candidate_reagent_count",
            "positive_reagent_count",
        )
        histograms = {
            f"{field}_histogram": dict(
                sorted(Counter(str(value[field]) for value in evaluation.values()).items())
            )
            for field in count_fields
        }
        rotations.append(
            {
                "rotation_id": rotation,
                "query_plate": query_plate,
                "gallery_plate": gallery_plate,
                "training_plates": train_plates,
                "training_plates_without_noncontrol_rows": empty_training_plates,
                "design_eligible": not gates,
                "design_blockers": gates,
                "execution_allowed": False,
                "training": _units(training),
                "query_population": _units(queries),
                "gallery_population": _units(gallery),
                "evaluable": _units(evaluable),
                "unevaluable_queries": len(queries) - len(evaluable),
                "reagents_without_evaluable_queries": len(query_ids - set(evaluable.broad_sample)),
                "reagents_with_any_unevaluable_query": int(
                    queries.loc[
                        ~queries.record_id.isin(evaluable.record_id), "broad_sample"
                    ].nunique()
                ),
                "unseen_query_reagent_groups": len(query_ids - training_ids),
                "exclusion_reason_counts_nonexclusive": dict(sorted(reasons.items())),
                "query_plate_controls_excluded": int(
                    (query_plate_rows & labeled & rows.is_control).sum()
                ),
                "query_plate_missing_labels_excluded": int((query_plate_rows & ~labeled).sum()),
                **histograms,
                "cross_role_overlap": {
                    "train_query_reagents": len(training_ids & query_ids),
                    "train_gallery_reagents": len(training_ids & gallery_ids),
                    "query_gallery_reagents": len(query_ids & gallery_ids),
                    "train_query_gene_annotation_groups": len(train_genes & query_genes),
                    "train_gallery_gene_annotation_groups": len(train_genes & gallery_genes),
                    "query_gallery_gene_annotation_groups": len(query_genes & gallery_genes),
                    "interpretation": (
                        "Reagent/gene overlap is allowed for seen-treatment transfer; "
                        "not unseen-target generalization."
                    ),
                },
            }
        )
        for record in rows.itertuples():
            if record.Assay_Plate_Barcode == query_plate:
                assigned = "query"
            elif record.Assay_Plate_Barcode == gallery_plate:
                assigned = "gallery"
            else:
                assigned = "training"
            if not record.broad_sample:
                exclusion = "missing_treatment_label"
            else:
                exclusion = "control" if record.is_control else ""
            assignments.append(
                {
                    "rotation_id": rotation,
                    "assigned_role": assigned,
                    "role": "excluded" if exclusion else assigned,
                    "record_id": record.record_id,
                    "plate": record.Assay_Plate_Barcode,
                    "well": record.well_position,
                    "reagent": record.broad_sample,
                    "gene": record.Metadata_gene,
                    "is_control": record.is_control,
                    "exclusion_reasons": exclusion,
                    "evaluable": False,
                    "candidate_count": "",
                    "positive_count": "",
                    "positive_record_ids": "[]",
                    "candidate_reagent_count": "",
                    "positive_reagent_count": "",
                    **evaluation.get(record.record_id, {}),
                }
            )
    canonical = rows[sorted(set(REQUIRED) | {"is_control"})].to_csv(
        index=False, lineterminator="\n"
    )
    summary = {
        "schema_version": 1,
        "status": STATUS,
        "plan_only": True,
        "execution_allowed": False,
        "split_policy": split_policy,
        "minimum_reagent_groups": {"training": min_train_groups, "evaluable": min_evaluable_groups},
        "candidate_rotations": 12,
        "design_eligible_rotations": sum(r["design_eligible"] for r in rotations),
        "mapping_selected_metadata_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        "input_rows": len(mapping),
        "selected_rows": len(rows),
        "out_of_scope_rows": len(mapping) - len(rows),
        "selected_missing_label_rows": int((~labeled).sum()),
        "selected_control_rows_with_labels": int((labeled & rows.is_control).sum()),
        "selected_noncontrol_population": _units(usable),
        "conditions": {name: rows.iloc[0][name] for name in CONDITIONS},
        "batch": BATCH,
        "upstream_normalization_scope": upstream_normalization_scope,
        "execution_blockers": [
            "scientific_design_and_thresholds_not_approved",
            "replicate_independence_not_established",
            "query_guard_and_query_information_policy_pending",
            "upstream_normalization_unknown"
            if upstream_normalization_scope == "unknown"
            else "source_batch_preprocessing_is_transductive",
        ],
        "normalization_note": (
            "No transformations were fitted. A new training-only scaler cannot undo "
            "upstream batch-global normalization or feature selection."
        ),
        "unit_note": (
            "Profile rows and repeated rotations are not independent biological units. "
            "Reagent IDs and recorded gene annotation groups are counted separately; "
            "culture independence is unknown."
        ),
        "gallery_rule": (
            "All labeled non-control rows on the gallery plate; exclude the query's "
            "well coordinate from every candidate before any aggregation. "
            "Row counts and distinct reagent counts are both reported."
        ),
        "proposed_candidate_aggregation": "mean_scores_after_filtering",
        "candidate_aggregation_note": (
            "Proposed scoring would average surviving candidate-row scores by reagent "
            "after masks. This planner computes neither scores nor score averages."
        ),
        "count_units": {
            "candidate_count": "profile_rows_after_masks",
            "positive_count": "profile_rows_after_masks",
            "candidate_reagent_count": "distinct_reagent_IDs_after_masks",
            "positive_reagent_count": "distinct_exact_reagent_IDs_after_masks_0_or_1",
        },
        "positive_rule": (
            "Exact reagent ID, different physical plate and different well coordinate, "
            "matched recorded conditions; query reagent must occur in training."
        ),
        "rotations": rotations,
    }
    return summary, pd.DataFrame(assignments)
